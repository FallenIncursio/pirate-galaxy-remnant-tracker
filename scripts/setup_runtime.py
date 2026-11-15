"""Prepare a portable local runtime from the operator's own client libraries."""
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
    return {parts[i]: parts[i+1].strip() for i in range(1,len(parts)-1,2)}


def quoted(value):
    return json.dumps(str(value),ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game',type=Path,required=True,help='Directory containing the tested JAR, log4j/ and mina/')
    parser.add_argument('--jre',type=Path,help='Optional Java runtime to copy; otherwise use --java/PATH')
    parser.add_argument('--java',type=Path,help='Installed Java 21 executable')
    parser.add_argument('--javac',type=Path,help='Installed JDK 21 compiler; defaults to PATH')
    parser.add_argument('--credentials',type=Path,required=True)
    parser.add_argument('--config',type=Path,default=ROOT/'config.toml')
    parser.add_argument('--backend',choices=('sandboxie','process'),default='sandboxie' if os.name=='nt' else 'process')
    parser.add_argument('--sandboxie-dir',type=Path,default=Path(os.environ.get('ProgramFiles',''))/'Sandboxie-Plus')
    args = parser.parse_args()
    if os.name!='nt': os.umask(0o077)
    root = args.config.resolve().parent
    destination = root/'data/runtime'
    if args.config.exists() or destination.exists():
        raise SystemExit('Configuration/runtime already exists. Existing installations are not overwritten.')
    if not args.credentials.is_file():
        raise SystemExit('Credential file does not exist')
    java_name = 'java.exe' if os.name=='nt' else 'java'
    java = args.jre/'bin'/java_name if args.jre else args.java or Path(shutil.which('java') or '')
    javac = args.javac or Path(shutil.which('javac') or '')
    if not java.is_file() or not javac.is_file():
        raise SystemExit('Provide Java 21 and a JDK 21 compiler via --jre/--java/--javac or PATH')
    for executable,pattern in ((java,r'version "21(?:[.\" ])'),(javac,r'javac 21(?:[.\s]|$)')):
        result=subprocess.run([str(executable),'-version'],capture_output=True,text=True,timeout=20)
        if result.returncode or not re.search(pattern,result.stdout+result.stderr):
            raise SystemExit('The collector requires Java 21 and javac 21')
    jar = args.game/'PirateGalaxy-test.jar'
    if hashlib.sha256(jar.read_bytes()).hexdigest()!=TESTED_JAR:
        raise SystemExit('Client JAR does not match the tested runtime profile')
    jars = [Path(jar.name)]
    for folder in ('log4j','mina'):
        entries=sorted((args.game/folder).glob('*.jar'))
        if not entries: raise SystemExit('Required client dependency directory is empty: '+folder)
        jars.extend(Path(folder)/p.name for p in entries)
    box,container='PirateGalaxyRemnants',root/'data/sandbox'
    if args.backend=='sandboxie':
        if os.name!='nt': raise SystemExit('Sandboxie requires Windows')
        ini=Path(os.environ['WINDIR'])/'Sandboxie.ini'
        sbie_ini=args.sandboxie_dir/'SbieIni.exe'
        if not sbie_ini.is_file() or not (args.sandboxie_dir/'Start.exe').is_file():
            raise SystemExit('Provide the Sandboxie Plus installation directory')
        before=ini.read_bytes();original=sections(before)
        if box in original: raise SystemExit('Dedicated Sandboxie box already exists; inspect it first')
    destination.mkdir(parents=True,mode=0o700)
    for relative in jars:
        (destination/relative).parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(args.game/relative,destination/relative)
    if args.jre:
        shutil.copytree(args.jre,destination/'jre')
        java_setting='jre/bin/'+java_name
    else:
        java_setting=str(java.resolve())
    manifest={'java':java_setting,'javac':str(javac.resolve()),
              'java_sha256':hashlib.sha256(java.read_bytes()).hexdigest(),
              'classpath':[p.as_posix() for p in jars],
              'hashes':{p.as_posix():hashlib.sha256((destination/p).read_bytes()).hexdigest() for p in jars}}
    (destination/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    if args.backend=='sandboxie':
        (root/'data/Sandboxie-before.ini').write_bytes(before)
        for key,value in [('Enabled','y'),('FileRootPath',str(container)),('DropAdminRights','y'),('AutoRecover','n'),('AutoDelete','n')]:
            subprocess.run([str(sbie_ini),'set',box,key,value],capture_output=True,check=True,timeout=20)
        after=sections(ini.read_bytes())
        if not all(after.get(key)==value for key,value in original.items()):
            raise SystemExit('An unrelated Sandboxie section changed; inspect configuration')
    config='''[tracker]
server = "Korell"
realm_id = 2
poll_seconds = 180
retention_days = 30

[runtime]
backend = BACKEND
credentials_file = CREDENTIALS
manifest = "data/runtime/manifest.json"

[paths]
data = "data"

[discord]
username = "Remnant Tracker"
webhook_environments = ["DISCORD_WEBHOOK_URL"]
'''.replace('BACKEND',quoted(args.backend)).replace('CREDENTIALS',quoted(args.credentials.resolve()))
    if args.backend=='sandboxie':
        config+='\n[sandbox]\nstart = '+quoted((args.sandboxie_dir/'Start.exe').resolve())+'\nbox = '+quoted(box)+'\nroot = "data/sandbox"\n'
    args.config.resolve().write_text(config,encoding='utf-8')
    print('Runtime prepared. Configure Discord in secrets.env, then run validate. No game session started.')


if __name__=='__main__': main()
