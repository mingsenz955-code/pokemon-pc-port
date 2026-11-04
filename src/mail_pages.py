"""In-game inbox, offline cache, background refresh and original panel controls."""
import queue,threading
from PIL import Image,ImageDraw,ImageEnhance
from csb_render import nine_slice
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
        inbox_page=[None]
        owner=self.ui_window
        def paint():
            self._page_wheel(wheel)
            box=Mailbox(self.state);messages=box.messages()
            page=Page(self,'BottomNode_1',size=(800,480),canvas_size=(800,480),offset=(400,240))
            art=page.layer
            page.layer=Image.new('RGBA',(800,480),(0,0,0,115))
            page.layer.alpha_composite(art)
            page.actions['close_Button']=self.close_ui
            draw=ImageDraw.Draw(page.layer)
            def sprite(name,rect,cap=None,enabled=True):
                x,y,right,bottom=rect;size=(right-x,bottom-y)
                image=self.data.image('res/UI/'+name+'.png')
                image=nine_slice(image,size,cap) if cap else image.resize(size,Image.Resampling.LANCZOS)
                if not enabled:image=ImageEnhance.Color(image).enhance(0.2)
                page.layer.alpha_composite(image,(x,y))
            def button(key,rect,label,action,enabled=True):
                sprite('button_blue_211',rect,enabled=enabled)
                draw.text(((rect[0]+rect[2])/2,(rect[1]+rect[3])/2-1),label,font=self.cocos_ui.font('',15),
                          fill='#fff6d5',anchor='mm',stroke_width=1,stroke_fill='#28576f')
                page.hit(key,rect,action if enabled else lambda:None)
            draw.text((400,59),'邮件',font=self.cocos_ui.font('',30),fill='#fff0c8',anchor='mm',
                      stroke_width=2,stroke_fill='#803d26')
            draw.text((86,110),f'收件箱   {len(messages)} 封',font=self.cocos_ui.font('',16),fill='#fff0c8')
            button('mail_refresh',(621,96,711,130),'刷新',refresh,not busy[0])
            sprite('bottom_scale_bg',(298,131,721,408),(31,30,39,38))
            for i,mail in enumerate(messages[offset[0]:offset[0]+5]):
                y=136+i*45;chosen=mail['id']==selected[0]
                sprite('pet_item_selected_bg' if chosen else 'pet_item_unselected_bg',(82,y,288,y+41))
                if mail['id'] not in box.data['read']:
                    sprite('button_about',(87,y+9,105,y+27))
                text_box(page,(110,y+9,277,y+38),mail['title'],self.cocos_ui.font('',16))
                page.hit('mail_row_'+str(i),(82,y,288,y+41),lambda m=mail:choose(m))
            button('mail_prev',(82,370,153,403),'上一页',lambda:turn(-5),offset[0]>0)
            button('mail_next',(217,370,288,403),'下一页',lambda:turn(5),offset[0]+5<len(messages))
            draw.text((185,385),f'{offset[0]//5+1}/{max(1,(len(messages)+4)//5)}',
                      font=self.cocos_ui.font('',13),fill='#fff0c8',anchor='mm')
            mail=next((m for m in messages if m['id']==selected[0]),None)
            if mail:
                text_box(page,(322,154,695,181),mail['title'],self.cocos_ui.font('',21))
                text_box(page,(322,184,695,205),'发件人  '+mail['sender'],self.cocos_ui.font('',13))
                draw.line((321,207,693,207),fill='#c9ab7e')
                gold=mail.get('set_gold')
                rewards='、'.join(self._item_data(r['item'])[0]+' ×'+str(r['count']) for r in mail['rewards']) if gold is None else ''
                limit=text_box(page,(322,220,692,346),mail['body']+('\n\n附件：'+rewards if rewards else ''),self.cocos_ui.font('',16),scroll[0])
                scroll[0]=min(scroll[0],limit)
                claimed=mail['id'] in box.data['claimed'];expired=box.expired(mail)
                has_attachment=bool(mail['rewards']) or gold is not None
                label='已领取' if claimed else '已过期' if expired else '领取附件' if has_attachment else '无附件'
                button('mail_claim',(559,351,692,389),label,lambda:claim(mail),has_attachment and not (claimed or expired))
            else:
                text_box(page,(323,179,690,315),'请选择左侧邮件。' if messages else '暂无邮件。联网刷新后可收取新邮件。',self.cocos_ui.font('',17))
            draw.text((86,416),'收件码  '+box.data['player_id'],font=self.cocos_ui.font('',11),fill='#fff0c8')
            draw.text((708,416),status[0],font=self.cocos_ui.font('',11),fill='#fff0c8',anchor='ra')
            page.publish()
            inbox_page[0]=page
        def choose(mail):
            selected[0]=mail['id'];scroll[0]=0;Mailbox(self.state).read(mail['id']);self.save();paint()
        def turn(delta):
            last=max(0,(len(Mailbox(self.state).messages())-1)//5)*5
            offset[0]=max(0,min(last,offset[0]+delta));paint()
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
                if self.ui_open and self.ui_window is owner and self.original_page is inbox_page[0]:paint()
            self.root.after(100,poll)
        paint();refresh()
