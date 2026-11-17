const cstimer = require('cstimer_module');

const scr = process.argv[2] || '';
const type = process.argv[3] || '333';

try {
    const svg = cstimer.getImage(scr, type);
    if (svg) {
        process.stdout.write(svg);
    }
} catch (e) {
    process.stderr.write(e.message || String(e));
}
