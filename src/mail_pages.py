"""In-game inbox, offline cache, background refresh and original panel controls."""
import queue,threading
from PIL import Image,ImageDraw
from event_runtime import Request
from mailbox_system import Mailbox,download

class MailPages:
    def mailbox_ui(self):
        if self.battle or self.runtime.running or self.ui_open:return
        Mailbox(self.state);self.save()
        self.open_ui(Request('openui','mailbox',0,{'parameters':{'uiid':64,'mailbox':True}}))

    def _mail_page(self,body,info):
        from original_pages import Page
        from pet_pages import text_box
        body.pack_forget();selected=[None];offset=[0];scroll=[0];status=[''];busy=[False]
        owner=self.ui_window
        def paint():
            self._page_wheel(wheel)
            box=Mailbox(self.state);messages=box.messages()
            page=Page(self,'PublicNoticeUI',visible={'confirm_Button':False})
            page.layer=Image.new('RGBA',(800,480),(0,0,0,140))
            page.hits.clear();page.buttons.clear()
            draw=ImageDraw.Draw(page.layer)
            draw.rounded_rectangle((55,30,745,450),radius=20,fill='#f4e8ce',outline='#a46632',width=4)
            draw.text((80,44),'邮箱',font=self.cocos_ui.font('',26),fill='#693100')
            draw.text((80,80),'收件码：'+box.data['player_id'],font=self.cocos_ui.font('',12),fill='#693100')
            def button(key,rect,label,action):
                draw.rounded_rectangle(rect,radius=9,fill='#36c8ef',outline='#167ba8',width=2)
                draw.text(((rect[0]+rect[2])/2,(rect[1]+rect[3])/2),label,font=self.cocos_ui.font('',16),fill='white',anchor='mm')
                page.hit(key,rect,action)
            button('mail_refresh',(570,45,650,78),'刷新',refresh)
            button('mail_close',(660,45,720,78),'关闭',self.close_ui)
            for i,mail in enumerate(messages[offset[0]:offset[0]+5]):
                y=113+i*52;chosen=mail['id']==selected[0]
                draw.rounded_rectangle((75,y,295,y+46),radius=7,fill='#edbd77' if chosen else '#dcc8a3')
                prefix='● ' if mail['id'] not in box.data['read'] else ''
                text_box(page,(83,y+4,286,y+42),prefix+mail['title'],self.cocos_ui.font('',14))
                page.hit('mail_row_'+str(i),(75,y,295,y+46),lambda m=mail:choose(m))
            button('mail_prev',(75,386,165,419),'上一页',lambda:turn(-5))
            button('mail_next',(185,386,275,419),'下一页',lambda:turn(5))
            mail=next((m for m in messages if m['id']==selected[0]),None)
            if mail:
                text_box(page,(320,110,714,150),mail['title']+'  · '+mail['sender'],self.cocos_ui.font('',19))
                gold=mail.get('set_gold')
                rewards='、'.join(self._item_data(r['item'])[0]+' ×'+str(r['count']) for r in mail['rewards']) if gold is None else ''
                text_box(page,(320,158,714,337),mail['body']+('\n\n附件：'+rewards if rewards else ''),self.cocos_ui.font('',16),scroll[0])
                claimed=mail['id'] in box.data['claimed'];expired=box.expired(mail)
                label='已领取' if claimed else '已过期' if expired else '领取附件' if mail['rewards'] or gold is not None else '无附件'
                button('mail_claim',(480,365,710,411),label,lambda:claim(mail))
            else:
                text_box(page,(325,160,710,310),'请选择邮件。' if messages else '暂无邮件。联网刷新后可收到管理员邮件，已缓存的邮件离线也可查看。',self.cocos_ui.font('',18))
            text_box(page,(80,425,710,447),status[0],self.cocos_ui.font('',12))
            page.publish()
        def choose(mail):
            selected[0]=mail['id'];scroll[0]=0;Mailbox(self.state).read(mail['id']);self.save();paint()
        def turn(delta):
            offset[0]=max(0,min(max(0,len(Mailbox(self.state).messages())-1),offset[0]+delta));paint()
        def wheel(event):scroll[0]=max(0,scroll[0]+(-55 if event.delta>0 else 55));paint();return 'break'
        def claim(mail):
            box=Mailbox(self.state)
            if mail['id'] in box.data['claimed'] or box.expired(mail):return
            if not mail['rewards'] and mail.get('set_gold') is None:return
            try:
                with self.state.transaction():
                    rewards=box.claim(mail['id'])
                    if not self.save():raise ValueError('保存失败，附件尚未领取。')
            except (ValueError,KeyError) as error:
                self._page_tip(str(error),paint);return
            paint()
            if rewards:self.show_reward('邮件附件',rewards)
        def refresh():
            if busy[0]:return
            busy[0]=True;status[0]='正在收取邮件…';paint();result=queue.Queue()
            def work():
                try:result.put((True,download()))
                except Exception as error:result.put((False,str(error)))
            threading.Thread(target=work,daemon=True).start()
            def poll():
                try:ok,value=result.get_nowait()
                except queue.Empty:self.root.after(100,poll);return
                busy[0]=False
                if ok:
                    try:Mailbox(self.state).merge(value);self.save();status[0]='收取完成。'
                    except (ValueError,KeyError) as error:status[0]=str(error)
                else:status[0]=value
                if self.ui_open and self.ui_window is owner:paint()
            self.root.after(100,poll)
        paint();refresh()
