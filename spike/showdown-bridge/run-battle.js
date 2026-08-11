// Spike: drive Pokemon Showdown's sim engine headlessly (no server) for one
// full Gen 9 Champions VGC 2026 Reg M-B battle, and print the omniscient
// protocol log so we can see exactly what information the engine exposes
// before designing this project's own BattleState/Observation types around it.
//
// Two independent RandomPlayerAI instances stand in for two agents, each
// only able to write to its own p1/p2 stream -- this is the same shape our
// real Agent.select_action() bridge will eventually use.
//
// Teams are sampled from Showdown's champions-mod random team generator and
// retried until they pass TeamValidator for the target format, rather than
// hand-authored -- Reg M-B's rules turned out to differ substantially from
// mainline VGC (see notes.md), so this sidesteps guessing at legal EV/item
// combinations by hand.
const { BattleStream, Teams, TeamValidator, getPlayerStreams } = require('pokemon-showdown');
const { RandomPlayerAI } = require('pokemon-showdown/dist/sim/tools/random-player-ai');

const FORMAT_ID = 'gen9championsvgc2026regmb';
const validator = new TeamValidator(FORMAT_ID);

function legalRandomTeam(label, maxTries = 500) {
	for (let i = 1; i <= maxTries; i++) {
		const team = Teams.generate('gen9championsrandombattle');
		const problems = validator.validateTeam(team);
		if (!problems) {
			console.error(`${label}: legal team found after ${i} tries -`, team.map(p => p.species).join(', '));
			return team;
		}
	}
	throw new Error(`${label}: could not find a legal team in ${maxTries} tries`);
}

const p1Team = legalRandomTeam('p1Team');
const p2Team = legalRandomTeam('p2Team');

const streams = getPlayerStreams(new BattleStream());

const p1 = new RandomPlayerAI(streams.p1);
const p2 = new RandomPlayerAI(streams.p2);
void p1.start();
void p2.start();

(async () => {
	for await (const chunk of streams.omniscient) {
		console.log(chunk);
	}
	console.error('--- stream ended ---');
})();

void streams.omniscient.write(
	`>start ${JSON.stringify({ formatid: FORMAT_ID })}\n` +
	`>player p1 ${JSON.stringify({ name: 'P1', team: Teams.pack(p1Team) })}\n` +
	`>player p2 ${JSON.stringify({ name: 'P2', team: Teams.pack(p2Team) })}`
);
