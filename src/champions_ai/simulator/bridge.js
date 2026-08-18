/**
 * Long-lived Showdown bridge.
 *
 * Reads line-delimited JSON commands on stdin, writes line-delimited JSON
 * events on stdout. One process serves many battles, so self-play doesn't pay
 * Node startup per battle.
 *
 * Every command is answered with a matching {"type":"sync","id":N} once the
 * simulator has finished emitting, giving the Python side a definite read
 * boundary instead of guessing with timeouts.
 *
 * Requests are forwarded verbatim: they carry canMegaEvo, per-move disabled,
 * trapped and lockedMove, which per ADR 0003 are taken from the engine rather
 * than recomputed.
 */
const readline = require('readline');
const { BattleStream, Dex, getPlayerStreams, Teams, TeamValidator } = require('pokemon-showdown');

let streams = null;
let battleStream = null;

function send(event) {
	process.stdout.write(`${JSON.stringify(event)}\n`);
}

function pump(stream, onLine) {
	void (async () => {
		try {
			for await (const chunk of stream) {
				for (const line of chunk.split('\n')) {
					if (line) onLine(line);
				}
			}
		} catch (err) {
			send({ type: 'error', message: String(err && err.message ? err.message : err) });
		}
	})();
}

function startBattle(msg) {
	battleStream = new BattleStream();
	streams = getPlayerStreams(battleStream);

	pump(streams.omniscient, (line) => send({ type: 'line', line }));

	for (const player of ['p1', 'p2']) {
		pump(streams[player], (line) => {
			if (line.startsWith('|request|')) {
				const payload = line.slice('|request|'.length);
				if (payload) send({ type: 'request', player, request: JSON.parse(payload) });
			} else if (line.startsWith('|error|')) {
				send({ type: 'error', player, message: line.slice('|error|'.length) });
			} else {
				// The player-visible view of the battle: opponent HP appears as a
				// percentage here, unlike the omniscient stream. Observations must
				// be built from this, never from `line` events.
				send({ type: 'sideline', player, line });
			}
		});
	}

	const spec = { formatid: msg.format };
	if (msg.seed) spec.seed = msg.seed;

	void streams.omniscient.write(
		`>start ${JSON.stringify(spec)}\n` +
		`>player p1 ${JSON.stringify(msg.p1)}\n` +
		`>player p2 ${JSON.stringify(msg.p2)}`
	);
}

function randomTeam(msg) {
	// Showdown's random generator isn't Reg M-B aware and regularly trips Item
	// Clause or event-legality, so sample until the validator agrees.
	const validator = new TeamValidator(msg.format);
	const generatorFormat = msg.generator || msg.format;
	for (let attempt = 1; attempt <= (msg.maxTries || 500); attempt++) {
		const team = Teams.generate(generatorFormat);
		if (!validator.validateTeam(team)) {
			// Export text as well as packed: the packed form is what the engine
			// needs, the export form is what the Python side parses into domain
			// objects, and only Showdown can convert between them.
			send({
				type: 'team',
				packed: Teams.pack(team),
				exported: Teams.export(team),
				attempts: attempt,
			});
			return;
		}
	}
	send({ type: 'error', message: `no legal ${msg.format} team found` });
}

function validateTeam(msg) {
	const team = Teams.import(msg.team);
	if (!team) {
		send({ type: 'error', message: 'could not parse team' });
		return;
	}
	const problems = new TeamValidator(msg.format).validateTeam(team);
	if (problems) {
		send({ type: 'invalid', problems });
		return;
	}
	send({ type: 'team', packed: Teams.pack(team), exported: Teams.export(team), attempts: 0 });
}

function dexDump(msg) {
	const dex = Dex.mod(msg.mod || 'champions');

	const species = {};
	for (const entry of dex.species.all()) {
		if (entry.isNonstandard) continue;
		species[entry.id] = {
			name: entry.name,
			types: entry.types,
			baseStats: entry.baseStats,
			abilities: Object.values(entry.abilities),
			weightkg: entry.weightkg,
			baseSpecies: entry.baseSpecies,
		};
	}

// Showdown carries a move's real effects in `secondary`/`secondaries`,
// `drain`, `recoil` and `self`. Dropping them at the dump left the Python side
// pricing every move as raw damage, which misvalues most of what a VGC player
// actually presses: Nuzzle is 20 BP and 100% paralysis, Icy Wind 55 BP and a
// guaranteed Speed drop, Flare Blitz 120 BP minus a third of it back.
function normaliseSecondary(entry) {
	if (!entry) return null;
	return {
		chance: entry.chance === undefined ? 100 : entry.chance,
		status: entry.status || null,
		volatileStatus: entry.volatileStatus || null,
		// `boosts` land on the target; `self.boosts` on the user.
		boosts: entry.boosts || {},
		selfBoosts: (entry.self && entry.self.boosts) || {},
	};
}

function moveSecondaries(entry) {
	const listed = [];
	if (entry.secondaries) {
		for (const secondary of entry.secondaries) listed.push(normaliseSecondary(secondary));
	} else if (entry.secondary) {
		listed.push(normaliseSecondary(entry.secondary));
	}
	return listed.filter(Boolean);
}

	const moves = {};
	for (const entry of dex.moves.all()) {
		if (entry.isNonstandard) continue;
		moves[entry.id] = {
			name: entry.name,
			type: entry.type,
			category: entry.category,
			basePower: entry.basePower,
			// `true` means the move bypasses accuracy checks entirely, which is
			// not the same as 100% -- null carries that across as "always hits".
			accuracy: entry.accuracy === true ? null : entry.accuracy,
			priority: entry.priority,
			target: entry.target,
			// Drives the engine's shared "stall" counter: a consecutive use
			// succeeds a third as often as the last. Dumped rather than
			// hand-listed on the Python side, because a hand-copied list of
			// engine facts is exactly what drifts.
			stallingMove: !!entry.stallingMove,
			secondaries: moveSecondaries(entry),
			// Both are [numerator, denominator] fractions of damage dealt.
			drain: entry.drain || null,
			recoil: entry.recoil || null,
			// Unconditional self-boosts, as distinct from a secondary's: Close
			// Combat always drops its own defences, it does not roll for it.
			selfBoosts: (entry.self && entry.self.boosts) || {},
			flags: Object.keys(entry.flags || {}),
		};
	}

	// Emit resolved multipliers rather than Showdown's damageTaken codes, so
	// the semantics are computed once here by the engine that owns them
	// instead of being reimplemented on the Python side.
	const types = dex.types.all().filter((t) => !t.isNonstandard).map((t) => t.name);
	const chart = {};
	for (const attacking of types) {
		chart[attacking] = {};
		for (const defending of types) {
			chart[attacking][defending] = dex.getImmunity(attacking, defending)
				? Math.pow(2, dex.getEffectiveness(attacking, defending))
				: 0;
		}
	}

	send({ type: 'dex', species, moves, types, chart });
}

const HANDLERS = {
	start: startBattle,
	dexdump: dexDump,
	randomteam: randomTeam,
	validateteam: validateTeam,
	choose: (msg) => {
		void streams[msg.player].write(msg.choice);
	},
	seed: () => send({ type: 'seed', seed: battleStream.battle.prngSeed }),
	quit: () => process.exit(0),
};

const rl = readline.createInterface({ input: process.stdin });

rl.on('line', (raw) => {
	if (!raw.trim()) return;
	let msg;
	try {
		msg = JSON.parse(raw);
	} catch (err) {
		send({ type: 'error', message: `bad JSON: ${raw}` });
		return;
	}

	const handler = HANDLERS[msg.cmd];
	if (!handler) {
		send({ type: 'error', message: `unknown command ${msg.cmd}` });
	} else {
		try {
			handler(msg);
		} catch (err) {
			send({ type: 'error', message: String(err && err.message ? err.message : err) });
		}
	}

	// The simulator runs synchronously, but stream delivery is promise-based:
	// let the microtask and macrotask queues drain so every event this command
	// produced is written before the caller is told it may stop reading.
	setImmediate(() => setImmediate(() => send({ type: 'sync', id: msg.id ?? null })));
});
