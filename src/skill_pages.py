"""Original SkillReplaceUI and SkillReplaceItemUI; explicit slot before debit."""
from event_runtime import Request

class SkillPages:
 def _native_skill_replace(self,body,info):
  from original_pages import Page
  body.pack_forget();parameters=dict(self.ui_parameters);uid=str(parameters['uid']);key=str(parameters['key'])
  pet=next(p for p in self.state.pets if p.uid==uid);scroll=parameters.get('scroll');passive=key in self.data.tables['Talent']
  keys=[str(v) for v in (pet.talents if passive else pet.skills) if not passive or 400200<=int(v)<400300]
  table='Talent' if passive else 'Skill';row=self.data.tables[table][key];selected=[0]
  def back():
   if parameters.get('back'):self.open_ui(Request('openui','skill-return',0,{'parameters':{'uiid':int(parameters['back'])}}))
   else:self.close_ui()
  def paint():
   current=self.data.tables[table][keys[selected[0]]] if keys else {}
   page=Page(self,'SkillReplaceUI',text={**self._money_text(),'petName_Text':self.data.tables['Pet'][pet.species]['name'],
    'lv_BitmapFontLabel':str(pet.level),'skillName_Text':row['name'],'info_Text':row.get('des',row['name']),
    'mySkillInfo_Text':current.get('des',current.get('name','请选择要替换的技能')),
    'energy_BitmapFontLabel':str(row.get('energyCost',0)),
    'cost_BitmapFontLabel':'x1' if scroll else 'x'+str(row.get('moneyCount',0))},
    resources={**self._money_icons(),'cost_Sprite':self._item_data(scroll or row.get('moneyId','700001'))[1]})
   area=next(r for k,r in page.rects.items() if k.endswith('/skill_ListView'))
   size=self.cocos_ui.layout('SkillReplaceItemUI')['tree']['size'];height=size[1]
   for i,old in enumerate(keys):
    data=self.data.tables[table][old];x,y=area[0],area[1]+i*height
    page.add('SkillReplaceItemUI',(x,y),prefix=f'replace_{i}/',clip=area,
      text={'skillName_Text':data['name'],'energy_BitmapFontLabel':str(data.get('energyCost',0))},
      visible={'selected_Image':i==selected[0],'energy_Text':not passive,'energy_BitmapFontLabel':not passive})
    page.hit(f'replace_slot_{i}',(x,y,area[2],y+height),lambda n=i:choose(n),area)
   page.actions.update({'confirm_Button':confirm,'close_Button':back})
   self.ui_window.protocol('WM_DELETE_WINDOW',back);self._page_wheel(None);page.publish()
  def choose(index):selected[0]=index;paint()
  def confirm():
   try:
    with self.state.transaction():
     self.state.learn_skill(uid,key,replace=selected[0],scroll=scroll)
     if not self.save():raise ValueError('保存失败，技能学习未完成。')
   except (ValueError,KeyError) as error:self._page_tip(str(error),paint);return
   back()
   if self.ui_open:self._page_tip('技能替换成功。',self.original_page.publish)
   else:self.scene_ui.show_tip('技能替换成功。')
  if not keys:self._page_tip('没有可替换的技能。',back)
  else:paint()
