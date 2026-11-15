"""Prepare owned local runtime inputs and a dedicated Sandboxie box."""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TESTED_JAR = '6e31366238a3cea74ce8757abfc721a4d956145566ad12b29aeff2b65abc9e66'


def sections(raw):
    text = raw.decode('utf-16' if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig')
    parts = re.split(r'^\[([^]\r\n]+)\]\s*$', text, flags=re.M)
    return {parts[i]: parts[i+1].strip() for i in range(1, len(parts)-1, 2)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--game', type=Path, required=True)
    parser.add_argument('--jre', type=Path, required=True)
    parser.add_argument('--javac', type=Path, required=True)
    parser.add_argument('--credentials', type=Path, required=True)
    args = parser.parse_args()
    jar = args.game / 'PirateGalaxy-test.jar'
    if hashlib.sha256(jar.read_bytes()).hexdigest() != TESTED_JAR:
        raise SystemExit('This client JAR has not been validated. Keep the tested runtime profile.')
    destination = ROOT / 'data/runtime'
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copy2(jar, destination / jar.name)
    jars = [jar.name]
    for folder in ('log4j', 'mina'):
        (destination / folder).mkdir(exist_ok=True)
        for path in sorted((args.game / folder).glob('*.jar')):
            shutil.copy2(path, destination / folder / path.name)
            jars.append(folder + '/' + path.name)
    if (destination / 'jre').exists():
        raise SystemExit('Runtime directory already prepared; inspect it before replacing Java')
    shutil.copytree(args.jre, destination / 'jre')
    manifest = {'java': 'jre/bin/java.exe', 'javac': str(args.javac.resolve()), 'classpath': jars,
                'hashes': {name: hashlib.sha256((destination / name).read_bytes()).hexdigest() for name in jars}}
    manifest['hashes']['jre/bin/java.exe'] = hashlib.sha256((destination / 'jre/bin/java.exe').read_bytes()).hexdigest()
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    box, container = 'PirateGalaxyRemnants', ROOT / 'data/sandbox'
    ini = Path(os.environ.get('WINDIR', r'C:\Windows')) / 'Sandboxie.ini'
    before = ini.read_bytes()
    original = sections(before)
    if box in original:
        raise SystemExit('Dedicated sandbox already exists; inspect configuration before continuing')
    (ROOT / 'data/Sandboxie-before.ini').write_bytes(before)
    sbie_ini = Path(r'C:\Program Files\Sandboxie-Plus\SbieIni.exe')
    for key, value in [('Enabled','y'),('FileRootPath',str(container)),('DropAdminRights','y'),('AutoRecover','n'),('AutoDelete','n')]:
        subprocess.run([str(sbie_ini),'set',box,key,value],capture_output=True,check=True,timeout=20)
    after = sections(ini.read_bytes())
    if not all(after.get(key) == value for key, value in original.items()):
        raise SystemExit('An unrelated Sandboxie section changed; inspect configuration')
    config = (ROOT / 'config.example.toml').read_text()
    config = config.replace(r'C:\private\PG Cred.txt', str(args.credentials.resolve()))
    config = config.replace(r'D:\PirateGalaxyRemnantTracker\data\sandbox', str(container))
    if not (ROOT / 'config.toml').exists():
        (ROOT / 'config.toml').write_text(config)
    print('Local runtime and dedicated sandbox prepared. No game session was started.')


if __name__ == '__main__':
    main()
