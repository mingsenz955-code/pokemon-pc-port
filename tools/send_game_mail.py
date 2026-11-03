"""Prepare admin mail in the public feed; --publish explicitly commits/pushes it."""
import argparse,json,uuid,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'src'))
from mailbox_system import validate
p=argparse.ArgumentParser();p.add_argument('--title',required=True);p.add_argument('--body',required=True)
p.add_argument('--reward',action='append',default=[],help='itemId=count, repeatable')
p.add_argument('--to',default='all',help='all or comma-separated player receipt codes')
p.add_argument('--expires-at');p.add_argument('--publish',action='store_true');a=p.parse_args()
path=ROOT/'distribution/mailbox.json';feed=json.loads(path.read_text('utf8'))
mail={'id':uuid.uuid4().hex,'title':a.title,'body':a.body,'sender':'游戏管理员','to':'all' if a.to=='all' else a.to.split(','),
      'expires_at':a.expires_at,'rewards':[{'item':r.split('=')[0],'count':int(r.split('=')[1])} for r in a.reward]}
feed['messages'].insert(0,mail)
validate(feed,json.loads((ROOT/'original-1.20.4/tables.json').read_text('utf8')))
path.write_text(json.dumps(feed,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
if a.publish:
 subprocess.run(['git','add','distribution/mailbox.json'],cwd=ROOT,check=True)
 subprocess.run(['git','commit','--only','distribution/mailbox.json','-m','Send game mail: '+mail['id']],cwd=ROOT,check=True)
 subprocess.run(['git','push','origin','HEAD:main'],cwd=ROOT,check=True)
print(json.dumps(mail,ensure_ascii=False,indent=2))
