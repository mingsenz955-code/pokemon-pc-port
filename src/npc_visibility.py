"""Native setNpcState is global by NPC ID, independent of current village."""
from collections import defaultdict


def value(state, map_id, kind, identifier, default=True):
    if int(kind)==2:
        key=f'global:2:{identifier}'
        if key in state.visible:
            return bool(state.visible[key])
    return bool(state.visible.get(f'{map_id}:{kind}:{identifier}',default))


def set_value(state, map_id, kind, identifier, visible):
    key=(f'global:2:{identifier}' if int(kind)==2 else f'{map_id}:{kind}:{identifier}')
    state.visible[key]=bool(visible)


def migrate(state):
    if state.presentation.get('global_npc_visibility_version',0)>=1:
        return
    candidates=defaultdict(list)
    for key,visible in list(state.visible.items()):
        parts=key.split(':')
        if len(parts)==3 and parts[0].isdigit() and parts[1]=='2':
            candidates[parts[2]].append(bool(visible))
    changed=[];ambiguous=[]
    for identifier,values in candidates.items():
        key=f'global:2:{identifier}'
        if key in state.visible:continue
        if len(set(values))==1:
            state.visible[key]=values[0];changed.append(identifier)
        else:
            # Legacy keys have no timestamps. Do not guess which contradictory
            # map-scoped write occurred last; retain the existing local fallback.
            ambiguous.append(identifier)
    state.presentation['global_npc_visibility_version']=1
    if changed or ambiguous:
        state.audit.append({'repair':'global-npc-visibility','migrated':changed,
                            'ambiguous':ambiguous})
