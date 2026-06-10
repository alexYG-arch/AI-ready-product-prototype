# 如何应用 v2.0 Prototype Projection Overlay

这个 overlay 只包含相对 v1.0 新增或修改的文件。

## 应用方式

在你的 v1.0 harness 根目录执行；如果仓库根下还有 `prd_subharness_v1_0/` 这一层，请进入该目录或指定目标目录，避免放错层级。

```bash
rsync -a /path/to/prd_subharness_v1_0_to_v2_0_prototype_overlay/ .
```

如果你使用 Git：

```bash
git checkout -b feat/prototype-projection-v2.0
rsync -a /path/to/prd_subharness_v1_0_to_v2_0_prototype_overlay/ .
git diff
```

## 应用后校验

```bash
pip install -r requirements-dev.txt
python scripts/prd_control/harnessctl.py status
python scripts/prd_control/prototypectl.py status
python scripts/prd_control/prototypectl.py validate-runtime
python scripts/prd_control/prototypectl.py validate-interactions
```
