"""Render actual read-only outcomes; never reconstruct facts from guessed values."""
from dataclasses import dataclass

@dataclass(frozen=True)
class Composed:
    text: str
    primary_completed: bool

def _clean(outcome):
    value=outcome.speech.strip()
    k=outcome.step.key
    # Only this known duplicate label at the metric boundary is redundant.
    # Do not rewrite arbitrary text, numeric values or units.
    if (k.family,k.target,k.metric)==("utility","g","balance"):
        value=value.replace("燃气燃气账户余额","燃气账户余额",1)
    return value

def compose(plan,run,label):
    if run.superseded:
        return Composed("查询会话已更新，请重新发送。",False)
    by_step={o.step:o for o in run.outcomes}
    lines=[]
    # Deduplicate complete identical lines, not individual numeric values.
    # Error messages retain the corresponding registered query label.
    def append(value):
        if value and value not in lines:
            lines.append(value)
    if plan.caveat:
        append(plan.caveat)
    primary_ok=True
    for step in plan.primary+plan.supplements:
        outcome=by_step.get(step)
        if outcome is None or outcome.kind=="error" or outcome.kind=="superseded":
            append(label(step)+"："+(outcome.error if outcome and outcome.error else "查询未完成。"))
            if step in plan.primary:
                primary_ok=False
            continue
        if outcome.kind=="skipped":
            if step in plan.primary:
                append(label(step)+"：查询未完成。")
                primary_ok=False
            continue
        if outcome.kind not in {"ok","data_gap","state_limit"}:
            append(label(step)+"：查询未完成。")
            if step in plan.primary:
                primary_ok=False
            continue
        value=_clean(outcome)
        if not value:
            append(label(step)+"：没有有效回复。")
            if step in plan.primary:
                primary_ok=False
        else:
            append(value)
    return Composed("\n".join(lines) or "没有可用的查询结果。",primary_ok)
