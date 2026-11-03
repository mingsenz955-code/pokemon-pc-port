"""Explicit PC removals; keep original event files and gameplay steps intact."""
REMOVED_SCENE_BUTTONS = frozenset({
    'right_left_5_Button', 'right_left_6_Button', 'right_left_7_Button',
    'community_Button', 'giftReceive_Button', 'rechargeReward_Button', 'timelimitGiftBag_Button',
})
# IDs, not list offsets: restored snapshots retain their original positions.
REMOVED_TUTORIAL_STEPS = {
    'pEvent5901002.json': frozenset(range(18, 22)),  # online rank unlock/introduction/menu wait
    'pEvent101003.json': frozenset(range(6, 9)),    # former mainUp shop-location menu
}

def removed_tutorial_step(event, step):
    kind = step.get('type')
    # PC edition has no forced lessons. Applying this in EventRuntime.next
    # also releases old saves whose pending request is a removed lesson.
    if kind in ('button', 'addteachnode', 'trialride'):
        return True
    if kind == 'wait' and int(step.get('parameters', {}).get('type', 0)) == 3:
        return True
    if kind == 'mainuivisible':
        return True
    return (int(step.get('id', -1)) in REMOVED_TUTORIAL_STEPS.get(event, ()) or
            step.get('type') == 'button' and step.get('nodekey') in REMOVED_SCENE_BUTTONS)
