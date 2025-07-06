# Thoughts on Code Understanding
First lets formulate what perfect code understanding looks like, as in the ideal case.
Each line of code is understood with:
1. Kinds of potential input values (locals and globals expected at the execution of that LOC)
2. Transformation of input values (what is done at that LOC, and maybe implementation details of that transformation)
3. Output values given input values (value assignment back to locals and globals in that LOC)

Perfect code understanding should have perfect knowledge of all LOCs in the codebase, with each LOC understanding satisfying the criteria above.
It should also be noted that knowledge of codepaths or higher codebase level knowledge is also important, and `3.` depends on `1.` and `2.`

---
Humans have memory capacity issues. Recently saved/retrieved memory is the most reliable, memory not recently visited becomes prone to hallucination (forgetting) unless the human makes an explicit effort do retrieval, to refresh that memory again. (And obviously the more you refresh certain memories, the less that memory is prone to hallucination)
Given this criteria, there has been various coding habits that aim to facilitate better code understanding, with most of it directed at the nuances of human memory capacity.

Some of these are:
- Debugger tools elucidates exactly the criteria.
- Print debugging to fetch `1.` and `3.` at runtime used to inductively figure out `2.`
- Lower total LOC means less LOC requiring full understanding
- Code abstraction as a tradeoff to decrease total LOC while maintaining strong `1.` and `3.` but sacrifices `2.`
- Typed languages to assist `1.` and `3.`
- Unittests and typechecking to offload code understanding to machine
- Well scoped code is always good, because it prunes the space of potential `1.`.

Still codebases are pretty big and it's still very cumbersome for a human to sift through every LOC, though effective in improving understanding.
It's still difficult for most humans to achieve full code understanding. For those who do manage to achieve it, they're likely maintainers of the codebase as they have indexed the entire codebase into their memory.

Some existing pitfalls:
- For `1.` specifically, it's easier to reason about in the start of the codepath rather than later. The more transformations values in the locals and globals have gone through, the more prone to error it becomes.
- Complicated non-linear code is harder to understand than linear ones. For example for code that does recursion many many times, it's very tedious to trace it LOC by LOC, so the expected values at the output of the recursion becomes blurry.

---
Some open questions
What about LLMs?
Is it possible to give perfect code understanding to a LLM at inference time?
Push a full debugger trace into the context window? How would it work?
Certainly LLMs have a different memory nuances compared to humans, so what would be some coding habits a LLM should use?