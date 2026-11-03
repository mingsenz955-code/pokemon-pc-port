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
    return (int(step.get('id', -1)) in REMOVED_TUTORIAL_STEPS.get(event, ()) or
            step.get('type') == 'button' and step.get('nodekey') in REMOVED_SCENE_BUTTONS)
