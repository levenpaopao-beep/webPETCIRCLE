"""启动本机前后台；不会部署到正式服务器。"""
import os,signal,subprocess,sys,urllib.request,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PYTHON=Path('/Users/levenwong/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3')
def alive(port,path):
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}{path}',timeout=2) as r:return r.status==200
    except Exception:return False
def main():
    children=[]
    if not alive(8790,'/api/health'):children.append(subprocess.Popen([str(PYTHON),'-m','server.app','--port','8790'],cwd=ROOT))
    if not alive(4173,'/'):children.append(subprocess.Popen(['npm','run','dev','--','--host','127.0.0.1','--port','4173','--strictPort'],cwd=ROOT/'web'))
    print('官网：http://127.0.0.1:4173/\n后台：http://127.0.0.1:4173/#/admin',flush=True)
    if not children:return
    def stop(*args):
        for p in children:
            if p.poll() is None:p.terminate()
        for p in children:p.wait()
        raise SystemExit(0)
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    try:
        while True:
            for p in children:
                if p.poll() is not None:stop()
            time.sleep(1)
    finally:
        for p in children:
            if p.poll() is None:p.terminate()
if __name__=='__main__':main()
