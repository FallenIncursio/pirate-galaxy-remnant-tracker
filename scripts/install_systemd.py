"""Install an unprivileged systemd user service; enable lingering for boot startup."""
import argparse
import getpass
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from pg_remnants.config import load

SERVICE='pirate-galaxy-remnants.service'


def unit_quote(value, *, command=False):
    value=str(value)
    if any(ord(c)<32 for c in value):
        raise ValueError('Control characters are not allowed in service paths')
    value=value.replace('\\','\\\\').replace('"','\\"').replace('%','%%')
    if command: value=value.replace('$','$$')
    return '"'+value+'"'


def unit_text(config, python):
    # No root, shell expansion, passwords, hostnames or device-specific paths in the template.
    return f'''[Unit]
Description=Pirate Galaxy Remnant Tracker
StartLimitIntervalSec=300
StartLimitBurst=5

[Service]
Type=simple
WorkingDirectory={unit_quote(config.parent)}
ExecStart={unit_quote(python,command=True)} -m pg_remnants --config {unit_quote(config,command=True)} run
Restart=on-failure
RestartPreventExitStatus=2
RestartSec=30
TimeoutStopSec=120
KillMode=mixed
UMask=0077
NoNewPrivileges=true
RestrictSUIDSGID=true
LockPersonality=true
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONDONTWRITEBYTECODE=1

[Install]
WantedBy=default.target
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',type=Path,default=ROOT/'config.toml')
    parser.add_argument('--python',type=Path,default=Path(sys.executable))
    parser.add_argument('--output',type=Path,help='Generate a unit for review without installing it')
    parser.add_argument('--enable-linger',action='store_true',help='Ask loginctl to keep this user service active at boot/logout')
    parser.add_argument('--start',action='store_true',help='Start or restart after installation')
    args=parser.parse_args();config=args.config.resolve()
    if load(config).backend!='process': raise SystemExit('systemd installation requires runtime.backend="process"')
    # Keep the venv path: resolving its Python symlink would select the system interpreter.
    python=args.python.absolute()
    if not python.is_file(): raise SystemExit('Python executable does not exist')
    text=unit_text(config,python)
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(text,encoding='utf-8');return
    if not sys.platform.startswith('linux') or os.geteuid()==0:
        raise SystemExit('Run this installer as the Linux user who will own the tracker, not root')
    target=Path(os.environ.get('XDG_CONFIG_HOME',str(Path.home()/'.config')))/'systemd/user'/SERVICE
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists() and target.read_text(encoding='utf-8')!=text:
        backup=target.with_suffix('.service.previous')
        if backup.exists(): raise SystemExit('An earlier service backup exists; review it before replacing the unit')
        backup.write_bytes(target.read_bytes())
    target.write_text(text,encoding='utf-8')
    subprocess.run(['systemctl','--user','daemon-reload'],check=True)
    subprocess.run(['systemctl','--user','enable',SERVICE],check=True)
    if args.enable_linger:
        subprocess.run(['loginctl','enable-linger',getpass.getuser()],check=True)
    if args.start:
        subprocess.run(['systemctl','--user','restart',SERVICE],check=True)
    linger=subprocess.run(['loginctl','show-user',getpass.getuser(),'-p','Linger','--value'],capture_output=True,text=True,check=True).stdout.strip()
    print('Service installed and enabled. Boot startup: '+('enabled (Linger=yes)' if linger=='yes' else 'requires loginctl enable-linger for this user'))


if __name__=='__main__': main()
