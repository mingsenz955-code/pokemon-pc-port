"""Offline-readable game mail with per-save receipts and remote public feed."""
import uuid,time,json
from datetime import datetime,timezone

FEED_URLS=('https://raw.githubusercontent.com/mingsenz955-code/pokemon-pc-port/main/distribution/mailbox.json',
           'https://cdn.jsdelivr.net/gh/mingsenz955-code/pokemon-pc-port@main/distribution/mailbox.json')
GOLD_ID='700001'

def validate(feed,tables):
    if not isinstance(feed,dict) or feed.get('format') not in (1,2):raise ValueError('邮件数据格式无效。')
    mails=feed.get('messages',[])
    if not isinstance(mails,list) or len(mails)>500:raise ValueError('邮件数量无效。')
    result=[];seen=set()
    for row in mails:
        if not isinstance(row,dict):raise ValueError('邮件条目无效。')
        kid=str(row['id']);title=str(row['title']);body=str(row.get('body',''))
        if not kid or kid in seen or len(kid)>128 or len(title)>100 or len(body)>12000:raise ValueError('邮件字段无效。')
        seen.add(kid);rewards=[]
        attachments=row.get('rewards',[])
        if not isinstance(attachments,list) or len(attachments)>20:raise ValueError('邮件附件无效。')
        for reward in attachments:
            if not isinstance(reward,dict):raise ValueError('邮件附件无效。')
            key=str(reward['item']);count=reward['count']
            if type(count) is not int or not 0<count<=100000000 or not any(key in tables.get(t,{}) for t in ('Money','Item','Pet')):raise ValueError('邮件附件无效。')
            if key in tables.get('Pet',{}) and count>6:raise ValueError('单封邮件宠物附件最多六只。')
            rewards.append({'item':key,'count':count})
        if len(rewards)>20:raise ValueError('邮件附件过多。')
        gold=row.get('set_gold')
        if gold is not None and (feed['format']!=2 or type(gold) is not int or not 0<=gold<=100000000
                                 or GOLD_ID not in tables.get('Money',{})
                                 or any(r['item'] in (GOLD_ID,'700003') for r in rewards)):
            raise ValueError('邮件金币设置无效。')
        target=row.get('to','all')
        if target!='all' and (not isinstance(target,list) or not all(isinstance(x,str) for x in target)):raise ValueError('收件人无效。')
        expires=row.get('expires_at')
        if expires:
            if not isinstance(expires,str):raise ValueError('邮件截止时间无效。')
            parsed=datetime.fromisoformat(expires.replace('Z','+00:00'))
            if parsed.tzinfo is None:raise ValueError('邮件截止时间必须包含时区。')
        result.append({'id':kid,'title':title,'body':body,'sender':str(row.get('sender','游戏管理员'))[:80],
                       'to':target,'expires_at':expires,'rewards':rewards,'set_gold':gold})
    return result

class Mailbox:
    def __init__(self,state):
        self.state=state
        state.activities.setdefault('mailbox',{'player_id':uuid.uuid4().hex,'messages':[], 'read':[], 'claimed':[]})
    @property
    def data(self):return self.state.activities['mailbox']
    def messages(self):
        return [m for m in self.data['messages'] if m['to']=='all' or self.data['player_id'] in m['to']]
    def merge(self,feed):
        messages=validate(feed,self.state.tables)
        existing={m['id']:m for m in self.data['messages']}
        fresh=[m for m in messages if m['id'] not in existing]
        self.data['messages']=(fresh+self.data['messages'])[:500]
    def expired(self,mail):
        value=mail.get('expires_at')
        return bool(value and datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(timezone.utc).timestamp()<=time.time())
    def read(self,kid):
        if kid not in self.data['read']:self.data['read'].append(kid)
    def claim(self,kid):
        mail=next((m for m in self.messages() if m['id']==kid),None)
        if not mail:raise ValueError('邮件不存在。')
        if kid in self.data['claimed']:raise ValueError('附件已领取。')
        if self.expired(mail):raise ValueError('邮件附件已过期。')
        gold=mail.get('set_gold')
        if not mail['rewards'] and gold is None:raise ValueError('这封邮件没有附件。')
        configs=list(mail.get('pet_configs') or [])
        pet_total=sum(r['count'] for r in mail['rewards'] if r['item'] in self.state.tables.get('Pet',{}))
        if configs and len(configs)!=pet_total:raise ValueError('宠物附件配置数量不一致。')
        with self.state.transaction():
            if configs:
                from game_state import Pet
                index=0
                for reward in mail['rewards']:
                    if reward['item'] in self.state.tables.get('Pet',{}):
                        for _ in range(reward['count']):
                            config=dict(configs[index]);index+=1
                            if str(config.get('species'))!=str(reward['item']):
                                raise ValueError('宠物附件配置与种类不一致。')
                            config['uid']=uuid.uuid4().hex
                            self.state.receive_pet(Pet(**config))
                    else:
                        self.state.grant(reward['item'],reward['count'])
            else:
                self.state.grant_many([r['item'] for r in mail['rewards']],[r['count'] for r in mail['rewards']])
            if gold is not None:self.state.inventory[GOLD_ID]=gold
            self.read(kid);self.data['claimed'].append(kid)
        return [(r['item'],r['count']) for r in mail['rewards']]

def download():
    import urllib.request
    for url in FEED_URLS:
        try:
            with urllib.request.urlopen(url,timeout=4) as response:
                data=response.read(262145)
                if len(data)>262144:raise ValueError('邮件数据过大。')
                return json.loads(data.decode('utf-8'))
        except Exception:continue
    raise ValueError('暂时无法连接，已保留本机缓存邮件。')
