/**
 * Optional postinstall pre-warm for @emend-ai/utim.
 *
 * This is a best-effort pre-installation of the UTIM Python engine.
 * If it fails for ANY reason, we exit 0 — the main launcher (bin/utim.js)
 * will handle installation automatically on first run with a clean spinner.
 *
 * This script exists purely to make the first `utim` launch faster
 * by pre-installing the Python engine during `npm install`.
 */
const { spawnSync } = require('child_process');
const os = require('os');
const fs = require('fs');

const isWin = os.platform() === 'win32';
const isTermux =
    (process.env.PREFIX && process.env.PREFIX.includes('com.termux')) ||
    fs.existsSync('/data/data/com.termux');

function findPython() {
    const candidates = isWin ? ['python', 'python3', 'py'] : ['python3', 'python'];
    for (const candidate of candidates) {
        try {
            const r = spawnSync(candidate, ['--version'], {
                encoding: 'utf8',
                timeout: 4000,
                shell: isWin,
                windowsHide: true,
            });
            const out = (r.stdout || '') + (r.stderr || '');
            if (out.includes('Python 3')) return candidate;
        } catch (_) {}
    }
    return null;
}

// Set execute bit on Unix / macOS / Termux
function setExecuteBit() {
    if (!isWin) {
        try {
            const binFile = require('path').join(__dirname, '..', 'bin', 'utim.js');
            fs.chmodSync(binFile, 0o755);
        } catch (_) {}
    }
}

setExecuteBit();

// Skip pre-warm on Termux — needs prebuilt pkg packages first,
// which the main launcher handles properly with user guidance.
if (isTermux) {
    process.exit(0);
}

const python = findPython();
if (!python) {
    // No Python — launcher will guide the user on first run
    process.exit(0);
}

// Read the version from package.json to pin the python engine version
const path = require('path');
let versionPin = '';
try {
    const pkg = require(path.join(__dirname, '..', 'package.json'));
    if (pkg.version) {
        versionPin = `==${pkg.version}`;
    }
} catch (_) {}

const pipPackage = `utim-cli${versionPin}`;

// Silently pre-install in the background (pipe output, not inherit)
// so the npm install output stays clean. Any failure is fine —
// the launcher self-heals on first `utim` run.
try {
    const r = spawnSync(
        python,
        ['-m', 'pip', 'install', '--quiet', pipPackage],
        {
            stdio: 'pipe',
            shell: isWin,
            windowsHide: true,
            timeout: 300000,
        }
    );
    if (r.status === 0) {
        console.log('\n✅  UTIM ready. Run  utim  to get started.\n');
    }
    // If it fails, stay silent — launcher will handle it
} catch (_) {}

process.exit(0);
