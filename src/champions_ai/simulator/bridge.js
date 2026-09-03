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
const { BattleStream, Dex, getPlayerStreams, PRNG, Teams, TeamValidator } = require('pokemon-showdown');

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

// Derive a distinct-but-deterministic seed for each sampling attempt.
// A fixed seed alone is not enough: the generator would hand back the same
// rejected team every time and the loop would spin to maxTries.
function seedForAttempt(base, attempt) {
	if (!base) return undefined;
	const comma = base.indexOf(',');
	if (comma < 0) return undefined;
	const prefix = base.slice(0, comma);
	const hex = base.slice(comma + 1);
	const bumped = (BigInt('0x' + hex) + BigInt(attempt))
		.toString(16)
		.padStart(hex.length, '0')
		.slice(-hex.length);
	return `${prefix},${bumped}`;
}

function randomTeam(msg) {
	// Showdown's random generator isn't Reg M-B aware and regularly trips Item
	// Clause or event-legality, so sample until the validator agrees.
	const validator = new TeamValidator(msg.format);
	const generatorFormat = msg.generator || msg.format;
	for (let attempt = 1; attempt <= (msg.maxTries || 500); attempt++) {
		const seed = seedForAttempt(msg.seed, attempt);
		const team = Teams.generate(generatorFormat, seed ? { seed } : null);
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
			// Purely visual variants -- Furfrou-Debutante, Unown-B, Shellos-East.
			// They share every stat with the base form and get no dex entry of
			// their own, so without this the Python side cannot look them up at
			// all even though they appear on real teams.
			cosmeticFormes: entry.cosmeticFormes || [],
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
			// Eleven moves in this dex carry a zero `basePower` because the
			// engine computes it per hit -- Low Kick from the target's weight,
			// Gyro Ball from the speed ratio. Without this flag they read as
			// status moves.
			dynamicPower: typeof entry.basePowerCallback === 'function',
			// Fixed-damage moves ignore the damage formula outright. Nine of
			// them here, all with a zero basePower and no basePowerCallback,
			// so `is_damaging` read every one -- Seismic Toss, Night Shade,
			// Super Fang -- as a status move.
			fixedDamage: entry.damage === undefined ? null : entry.damage,
			damageCallback: typeof entry.damageCallback === 'function',
			// Some moves swing with, or land on, a stat their category does
			// not imply: Body Press is Physical but uses the user's Defense,
			// Psyshock is Special but hits the target's Defense, Foul Play
			// swings with the *target's* Attack. Dumped as nulls rather than
			// omitted, so "no override" is a fact rather than a gap.
			overrideOffensiveStat: entry.overrideOffensiveStat || null,
			overrideDefensiveStat: entry.overrideDefensiveStat || null,
			overrideOffensivePokemon: entry.overrideOffensivePokemon || null,
			// Freeze-Dry is Ice and hits Water for 2x; Flying Press is
			// Fighting and applies Flying on top. Neither is expressible in a
			// type chart, and the callback cannot be dumped -- so flag them,
			// and let a test fail if this dex ever carries one we have not
			// written a rule for.
			overridesEffectiveness: typeof entry.onEffectiveness === 'function',
			secondaries: moveSecondaries(entry),
			// Both are [numerator, denominator] fractions of damage dealt.
			drain: entry.drain || null,
			recoil: entry.recoil || null,
			// Unconditional self-boosts, as distinct from a secondary's: Close
			// Combat always drops its own defences, it does not roll for it.
			selfBoosts: (entry.self && entry.self.boosts) || {},
			flags: Object.keys(entry.flags || {}),
			// --- what a move does besides the damage roll ---
			// A move's own effects, as distinct from a secondary's rider.
			// `boosts` is the entire point of Swords Dance and was not dumped
			// at all, so every one of the 175 status moves here scored the
			// same flat value as every other.
			boosts: entry.boosts || null,
			status: entry.status || null,
			volatileStatus: entry.volatileStatus || null,
			// [numerator, denominator] of the user's max HP.
			heal: entry.heal || null,
			sideCondition: entry.sideCondition || null,
			slotCondition: entry.slotCondition || null,
			weather: entry.weather || null,
			terrain: entry.terrain || null,
			pseudoWeather: entry.pseudoWeather || null,
			// --- what changes the damage itself ---
			// A number, or [min, max]. A 2-5 hit move lands about 3.1 times,
			// so predicting one hit understates it threefold.
			multihit: entry.multihit === undefined ? null : entry.multihit,
			// Each hit of these rolls accuracy separately.
			multiaccuracy: !!entry.multiaccuracy,
			// Dragon Darts fires one of its two hits at *each* opponent in
			// doubles rather than both at one, so a plain multi-hit reading
			// doubles it.
			smartTarget: !!entry.smartTarget,
			// 1 is the ordinary 1/24. Higher means a wider crit stage.
			critRatio: entry.critRatio === undefined ? null : entry.critRatio,
			willCrit: entry.willCrit === undefined ? null : entry.willCrit,
			ohko: entry.ohko === undefined ? null : entry.ohko,
			ignoreDefensive: !!entry.ignoreDefensive,
			ignoreEvasion: !!entry.ignoreEvasion,
			ignoreImmunity: entry.ignoreImmunity === undefined ? null : !!entry.ignoreImmunity,
			breaksProtect: !!entry.breaksProtect,
			// Weather Ball, Terrain Pulse, Raging Bull and Aura Wheel change
			// their own *type*, so the chart lookup uses the wrong row.
			modifiesType: typeof entry.onModifyType === 'function',
			// --- who is left standing afterwards ---
			forceSwitch: !!entry.forceSwitch,
			selfSwitch: entry.selfSwitch === undefined ? null : entry.selfSwitch,
			selfdestruct: entry.selfdestruct || null,
			hasCrashDamage: !!entry.hasCrashDamage,
			thawsTarget: !!entry.thawsTarget,
		};
	}

	// Held items. Their effects live in JavaScript callbacks and cannot be
	// dumped, so what is carried across is *identity*: which items exist, and
	// the structural facts the engine does expose. The multipliers themselves
	// are transcribed on the Python side and guarded by a test that every id
	// in that table appears here.
	const items = {};
	for (const entry of dex.items.all()) {
		if (entry.isNonstandard) continue;
		items[entry.id] = {
			name: entry.name,
			isBerry: !!entry.isBerry,
			// Locks its holder into one move, and boosts a stat by 1.5x.
			isChoice: !!entry.isChoice,
			// A Mega Stone changes species, stats and ability mid-turn. The
			// engine stores it as { base: resultingForme }, and dumping only
			// the key threw away the half that says *what it becomes* --
			// Charizardite X and Y both read "Charizard" and were
			// indistinguishable. Both halves now.
			megaStone: entry.megaStone ? Object.keys(entry.megaStone)[0] : null,
			megaForme: entry.megaStone ? Object.values(entry.megaStone)[0] : null,
			// Arceus plates carry the type they boost as data rather than code.
			plateType: entry.onPlate || null,
			// Thick Club and Light Ball only work for named species.
			itemUser: entry.itemUser || [],
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

	send({ type: 'dex', species, moves, items, types, chart });
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
	// Replace the random number generator mid-battle. This is what makes a
	// fork branch: replaying the same seed and the same choices reproduces a
	// position exactly, and every rollout from it would then be identical.
	// Reseeding at the branch point is what turns one position into a sample.
	// `battle.prngSeed` is a field captured at construction and never updated,
	// and `battle.resetRNG()` writes a "|message|" line into the protocol that
	// the trackers would have to learn to ignore. Setting the generator and
	// reading back its own starting seed does neither.
	reseed: (msg) => {
		battleStream.battle.prng = new PRNG(msg.seed);
		send({ type: 'seed', seed: battleStream.battle.prng.startingSeed });
	},
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
