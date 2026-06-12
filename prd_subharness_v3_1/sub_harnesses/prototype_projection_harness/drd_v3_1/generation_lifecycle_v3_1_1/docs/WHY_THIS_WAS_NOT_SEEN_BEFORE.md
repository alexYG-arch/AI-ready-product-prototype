# 为什么之前没遇到 generate 缺失，只遇到规则缺失

这个问题之前不明显，是因为早期 stage 中有一些“隐式生成能力”，所以系统看起来像是在运行，实际依赖的是 stage 内部自然语言 Required Operations 或既有 renderer 逻辑。

## 1. 早期 stage 有隐式生成动作

例如 RND-02 Full Canvas Skeleton 在 2.1 文档中已经明确要求创建 Figma page / section / screen placeholder / state placeholder / overlay placeholder / route corridor / annotation target zones。也就是说，这个 stage 虽然没有单独叫 generator，但它已经写了 Required Operations，具备隐式生成能力。

因此早期问题表现为：

```text
生成出来了，但细节不够
→ 缺规则
```

而不是：

```text
根本没有产物
→ 缺 generator
```

## 2. 新增 stage 是抽象治理层，没有历史 renderer 实现兜底

后来新增了 Screen Role、Design Kernel、Composition、Hotspot、Logic Sidecar Audit、Repair Crew 等阶段。这些阶段是新抽象，并没有旧 renderer 代码或旧 Figma 构建逻辑兜底。

所以它们如果只写：

```text
Required Rules
Blocks If
Validators
Repair Actions
```

而不写：

```text
Generate Algorithm
Minimum Viable Output
Generation Worker
Generation Trace
```

运行时就会直接出现：

```text
artifact missing
→ validator block
```

## 3. 缺规则和缺生成是两个不同层级的问题

缺规则意味着：

```text
系统能生成东西，但生成得不够好、不够细、不够受控。
```

缺生成意味着：

```text
系统连第一版可校验产物都没有。
```

v3.1 之前主要在补规则、loop 和 repair，所以常见问题是“缺规则”。v3.1 引入 repair crew 后，系统开始真正按 artifact 工作，于是发现某些 artifact 从未被生成，问题才暴露成“缺 generate”。

## 4. 结论

这不是局部 bug，而是生命周期缺层：

```text
Rule 不能替代 Generator。
Validator 不能替代 Generator。
Repair Crew 不能替代 Build Crew。
```

正确生命周期必须是：

```text
Generate → Self-check → Validate → Repair → Revalidate
```
