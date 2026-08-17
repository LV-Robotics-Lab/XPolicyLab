# Prometheus source adapter

XPolicyLab is a dispatcher over many independent policy integrations. This
directory exposes that fact to Prometheus instead of pretending the repository
has one environment, trainer, resume format, or distributed runtime.

The adapter is a source-side capability declaration, not a source pin. The
consuming Prometheus `policy/xpolicy_lab` branch records the exact gitlink SHA.

Run the dependency-free structural checks:

```bash
python .prometheus/adapter.py capabilities
python .prometheus/adapter.py doctor --policy-name demo_policy
```

Plan one existing policy script without executing it:

```bash
python .prometheus/adapter.py train \
  --policy-name demo_policy \
  --plan -- RoboDojo demo arx_x5 joint 0 0
```

`policy_name` is restricted to one direct child of `policy/`; separators,
traversal, whitespace, and shell punctuation are rejected. Dispatch uses an
argv array (`bash`, repository-relative script, native arguments), never a
constructed shell command.

Preparation, training, evaluation, serving, environments, and distributed
execution remain per-policy. A stage fails closed when the selected policy
does not provide its standard script. There is no honest generic resume or
export stage, so neither is exposed.

Robot/action dimensions remain owned by XPolicyLab's selected adapter and its
parent workspace. This directory intentionally contains no copied registry.
Training or serving a model does not authorize hardware rollout.
