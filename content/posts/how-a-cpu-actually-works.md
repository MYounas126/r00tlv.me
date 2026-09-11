---
title: "How a CPU actually works"
date: 2026-09-11T01:00:00+05:00
categories: ["Notes"]
tags: ["assembly", "x86-64", "reverse-engineering", "fundamentals"]
description: "A CPU only does four things. All four are animated on this page. Once you can see them, assembly stops being intimidating and becomes vocabulary."
summary: "A CPU only does four things. All four are animated on this page. Once you can see them, assembly stops being intimidating and becomes vocabulary."
cover:
  image: "/img/posts/re/cpu-die.webp"
  alt: "Die shot of an Intel 80486DX2"
  hiddenInSingle: true
ShowToc: true
TocOpen: false
---

Every diagram on this page is animated. Watch the movement first and read the words second. If a section feels hard, the animation is the answer, not the paragraph.

Do not try to memorise instructions. Nobody does that. There is a plain-English glossary at the bottom for any word that feels made up.

## The one picture

A computer is a notebook and a very fast, very stupid clerk.

The notebook is memory. Every line has a number. The clerk reads one line, does exactly what it says, then looks at the next line. The clerk has a few sticky notes on the desk for scratch work: those are registers. One sticky note is special. It says which line to read next. That is the instruction pointer.

That is genuinely the whole machine. Everything else is detail.

<img src="/img/posts/cpu/cpu-01-memory-is-paper.svg" alt="Memory as a numbered notebook, with an orange arrow marking the current line" width="820" height="440" loading="lazy" decoding="async" style="max-width:100%;height:auto;aspect-ratio:820/440">

Watch the orange arrow. It is not decoration. That arrow is the instruction pointer, and the address next to it is the line number it is holding.

| Machine width | Name of that register |
| :--- | :--- |
| 16-bit | `IP` |
| 32-bit | `EIP` |
| 64-bit | `RIP` |

Same register. `E` means extended, `R` means 64-bit. You will see all three in writeups.

## The loop that is the entire CPU

<img src="/img/posts/cpu/cpu-03-fetch-decode-execute.svg" alt="The fetch, decode, execute cycle with a highlight moving between stages" width="820" height="340" loading="lazy" decoding="async" style="max-width:100%;height:auto;aspect-ratio:820/340">

Read the line. Work out what it means. Do it. Move on. Repeat a few billion times a second.

There is no step five.

Here is why that one idea matters more than everything else on this page. Nothing happens on a computer unless RIP points at it. So the goal of exploitation is not complicated:

**Make RIP point at something you chose.**

Buffer overflows, ROP, format strings, use-after-free are all different roads to that same place. Keep that sentence in your head for everything below.

## Thing 1 of 4: registers

Registers are the CPU's variables. You get about sixteen useful ones, they are built into the chip, and they are the only place arithmetic actually happens.

<img src="/img/posts/cpu/cpu-02-registers-and-flags.svg" alt="Registers changing value as instructions execute, with the zero flag flipping at the end" width="820" height="430" loading="lazy" decoding="async" style="max-width:100%;height:auto;aspect-ratio:820/430">

Watch `EAX` change with each instruction, then watch the zero flag flip to 1 at the end.

| Instruction | Plain English |
| :--- | :--- |
| `mov eax, 5` | put 5 in EAX. `mov` means copy, the source is not emptied |
| `add eax, 3` | EAX = EAX + 3 |
| `sub eax, ebx` | EAX = EAX - EBX |

The answer always lands in the left-hand operand. That is the rule for nearly every instruction here.

### What the sixteen are for

Do not memorise this. Look at it, then come back when you meet a name you do not recognise.

| Register | What it is usually doing |
| :--- | :--- |
| `rax` | general work, and the return value of a function |
| `rbx`, `r10` to `r15` | general work |
| `rcx`, `rdx`, `rsi`, `rdi`, `r8`, `r9` | general work, and function arguments |
| `rsp` | stack pointer, always points at the top of the stack |
| `rbp` | base pointer, marks the bottom of the current stack frame |
| `rip` | instruction pointer, what runs next |
| `rflags` | the flags, set automatically by arithmetic |

### Why the same register has four names

This confuses everyone, so it gets its own animation.

<img src="/img/posts/cpu/cpu-10-register-windows.svg" alt="rax, eax, ax and al shown as four windows onto the same eight bytes" width="820" height="400" loading="lazy" decoding="async" style="max-width:100%;height:auto;aspect-ratio:820/400">

`rax`, `eax`, `ax` and `al` are not four registers. They are four windows onto the same eight bytes.

| Name | Size | Which part |
| :--- | :--- | :--- |
| `rax` | 64-bit | all of it |
| `eax` | 32-bit | the lower half |
| `ax` | 16-bit | the lower quarter |
| `al` | 8-bit | the lowest byte |

"Lower" always means the least-significant end. The same pattern applies to every register: `rbx`/`ebx`/`bx`/`bl`, and `r8`/`r8d`/`r8w`/`r8b`.

### The one trap worth learning before it bites you

<img src="/img/posts/cpu/cpu-11-zero-extension-trap.svg" alt="Writing to a 32-bit register zeroing the upper half, while an 8-bit write leaves it intact" width="820" height="420" loading="lazy" decoding="async" style="max-width:100%;height:auto;aspect-ratio:820/420">

Writing to a 32-bit register wipes the top half of the 64-bit register to zero. Writing to an 8-bit or 16-bit one does not.

```asm
mov eax, 1    ; rax is now 0x0000000000000001   <- top half destroyed
mov al, 1     ; rax is now 0xFFFFFFFFFFFFFF01   <- top half untouched
```

When you are reading disassembly and a register mysteriously changed, this is almost always the reason.

### Flags

Every `add`, `sub` and `cmp` quietly sets a few flags as a side effect. The one that matters first is the zero flag: it turns on when the last answer was 0. That single on/off bit is what makes decisions possible.

## Thing 2 of 4: memory

Sixteen variables will not get you far. A game's player position, lives, every coin, every enemy: all of that lives in memory, and only visits a register when the CPU needs to work on it.

<img src="/img/posts/cpu/cpu-04-load-and-store.svg" alt="Load moving a value from memory into a register, and store moving it back" width="820" height="400" loading="lazy" decoding="async" style="max-width:100%;height:auto;aspect-ratio:820/400">

```asm
mov eax, [0x4005db]     ; LOAD  : memory  -> register
mov [0x4005e3], eax     ; STORE : register -> memory
```

The square brackets mean exactly what they mean in Python. `my_list[5]` gets element 5. `[0x4005db]` gets whatever is at address `0x4005db`. An address is just a very large index, because memory is a very large array of bytes numbered from zero.

Memory is to assembly what the disk is to a Python program. You pull things out into variables, do something with them, and eventually put them back.

### The brackets can do maths, and that is just arrays

<img src="/img/posts/cpu/cpu-13-addressing-modes.svg" alt="Base plus index times scale plus offset resolving to a single address" width="820" height="420" loading="lazy" decoding="async" style="max-width:100%;height:auto;aspect-ratio:820/420">

When you see `[rbx + rcx*4 + 8]`, do not panic. It is `array[i]` written out longhand.

| Part | Means |
| :--- | :--- |
| base (`rbx`) | where the array starts |
| index (`rcx`) | which element you want |
| scale (`4`) | how many bytes each element takes |
| offset (`8`) | a fixed extra step, for example skipping a header |

The scale is always 1, 2, 4 or 8, because that is the size of a `char`, `short`, `int` or pointer. The CPU does the whole multiply-and-add for free, inside one instruction.

### Why everyone obsesses over keeping things in registers

<img src="/img/posts/cpu/cpu-09-speed-hierarchy.svg" alt="The latency gap between registers, cache levels and main memory" width="820" height="400" loading="lazy" decoding="async" style="max-width:100%;height:auto;aspect-ratio:820/400">

Registers are effectively free. Main memory costs a couple of hundred cycles. That gap is why caches exist, and in the modern world it is also why timing leaks secrets. Spectre and Meltdown are built on the fact that a cache hit and a cache miss take measurably different amounts of time.

## Thing 3 of 4: the stack

<img src="/img/posts/cpu/cpu-05-stack-push-pop.svg" alt="Push lowering the stack pointer and writing a value, pop raising it and leaving the bytes behind" width="820" height="470" loading="lazy" decoding="async" style="max-width:100%;height:auto;aspect-ratio:820/470">

The stack grows downward, toward smaller addresses.

| Operation | What actually happens |
| :--- | :--- |
| `push 5` | RSP goes down by 8, then 5 is written at the new RSP |
| `pop eax` | the value at RSP is copied into EAX, then RSP goes up by 8 |

`RSP` always points at the top item. Think of a stack of plates: you only ever add or take from the top.

Now the detail in that animation that most tutorials skip. **`pop` does not erase anything.** Look at the numbers that turn grey. They are still in memory, byte for byte. All `pop` does is move RSP back up, so that space is now considered free.

That leftover data is a real and constantly exploited bug class. Uninitialised variables, where a function reads stack space it never wrote and gets the previous function's leftovers. Memory disclosure, where those leftovers get sent back to you and leak addresses, defeating ASLR. Heartbleed was this shape of bug: read more than was written, receive whatever happened to be lying there.

## Thing 4 of 4: control flow, which is only ever writing to RIP

A CPU that could only run top to bottom could not loop, branch or call a function. So some instructions change RIP directly. That is all a jump is.

```asm
jmp 0x401050        ; roughly: mov rip, 0x401050
```

### Making a decision

<img src="/img/posts/cpu/cpu-07-conditional-branch.svg" alt="The same code taking two different paths depending only on the zero flag" width="820" height="450" loading="lazy" decoding="async" style="max-width:100%;height:auto;aspect-ratio:820/450">

Same code, run twice. Only the flag differs, and the path changes completely.

Here is the bit that makes `je` finally click. How do you check if two numbers are equal when all you have is arithmetic? Subtract them. If the answer is 0, they were equal.

So `cmp eax, ebx` is just a `sub` that throws the answer away and keeps only the flags. Then `je`, "jump if equal", really means "jump if the zero flag is set". The name says the intent, the mechanism is the flag.

| Instruction | Jumps when |
| :--- | :--- |
| `je` / `jz` | the two were equal (zero flag set) |
| `jne` / `jnz` | they were not equal |
| `jg`, `jl` | greater than, less than (signed) |
| `ja`, `jb` | above, below (unsigned) |

Every `if`, `while` and `for` you have ever written becomes this pair: one instruction that sets a flag, one that reads it.

### Calling a function

A function can be called from twenty different places, so it cannot hard-code the way back. The way back has to be stored somewhere. It gets stored on the stack.

<img src="/img/posts/cpu/cpu-06-call-and-ret.svg" alt="call pushing a return address then jumping, ret popping it back into RIP" width="820" height="470" loading="lazy" decoding="async" style="max-width:100%;height:auto;aspect-ratio:820/470">

```
call  =  push (address of the next instruction)  +  jmp
ret   =  pop that address back into RIP
```

`call` leaves a breadcrumb. `ret` follows it home. That is the entire mechanism.

Now watch that animation again, but as an attacker.

The return address is just data. It sits in memory. It sits right next to the buffers that functions write your input into. If you can write past the end of a buffer, you reach the saved return address. Overwrite it, and when `ret` runs it pops **your** value into RIP.

Remember the goal: make RIP point at something you chose. `ret` will do it for you, happily, because it cannot tell your value from the one `call` saved. That is a stack buffer overflow in two sentences.

Every mitigation you have heard of defends this one moment. Stack canaries detect the overwrite. ASLR hides the target. NX stops your data being runnable. CFI checks the destination is legal.

### How arguments get in and results get out

<img src="/img/posts/cpu/cpu-12-calling-convention.svg" alt="Arguments being placed in rdi, rsi, rdx before a call, and the result arriving in rax" width="820" height="430" loading="lazy" decoding="async" style="max-width:100%;height:auto;aspect-ratio:820/430">

There are no parameters down here. Arguments are agreed-upon registers, filled in just before the `call`.

| Argument | Register (Linux / macOS) |
| :--- | :--- |
| 1st | `rdi` |
| 2nd | `rsi` |
| 3rd | `rdx` |
| 4th | `rcx` |
| 5th | `r8` |
| 6th | `r9` |
| 7th and beyond | pushed on the stack |
| return value | `rax` |

This ordering is called a calling convention, and it is an agreement rather than a hardware rule. Linux and macOS use the order above. Windows x64 uses a different one: `rcx`, `rdx`, `r8`, `r9`. Same idea, different agreement.

This is also why a decompiler can label arguments at all. It sees which registers a function reads before it writes them.

## And none of it is text

<img src="/img/posts/cpu/cpu-08-assembly-is-just-numbers.svg" alt="The instruction mov eax, 5 shown as the bytes B8 05 00 00 00 in memory" width="820" height="430" loading="lazy" decoding="async" style="max-width:100%;height:auto;aspect-ratio:820/430">

`mov eax, 5` does not exist in memory. `B8 05 00 00 00` exists in memory.

`B8` is the opcode, meaning "load the next 4 bytes into EAX". `05 00 00 00` is the number, stored little-endian, smallest byte first, so it reads as `0x00000005`.

A disassembler turns those bytes back into text you can read. It is a convenience, not the truth.

Three consequences that matter enormously later:

**Patching a program means changing bytes.** Flip `74` (`je`) to `75` (`jne`) and you have inverted a licence check.

**x86 instructions are not a fixed length.** They run from 1 to 15 bytes. Start disassembling at a different offset and you get a completely different, still-valid program. That is why disassemblers can be fooled.

**Code and data are the same bytes.** Nothing marks a byte as an instruction. The CPU runs whatever RIP points at, which is exactly why controlling RIP is so powerful, and why NX had to be invented to say "these bytes are data, refuse to run them".

## The whole instruction set you need right now

Genuinely. This table plus the four ideas above will get you a long way.

| Instruction | Does |
| :--- | :--- |
| `mov dst, src` | copy |
| `add` / `sub` | arithmetic, result into the left operand |
| `inc` / `dec` | add 1 / subtract 1 |
| `imul` / `idiv` | multiply / divide |
| `and` / `or` / `xor` / `not` | bitwise logic. `xor rax, rax` is the idiomatic "set to 0" |
| `cmp a, b` | subtract, keep only the flags |
| `test a, b` | bitwise AND, keep only the flags. `test rax, rax` asks "is it zero?" |
| `jmp` | go there, always |
| `je` / `jne` / `jg` / `jl` | go there, if the flags say so |
| `call` / `ret` | call a function / return from one |
| `push` / `pop` | put on / take off the stack |
| `lea dst, [expr]` | work out the address, but do not read memory. Often used as fast arithmetic |
| `nop` | do nothing (opcode `0x90`, worth recognising) |
| `syscall` | ask the operating system to do something |

## Glossary

| Word | What it actually means |
| :--- | :--- |
| Register | A variable built into the CPU. Tiny, fast, about sixteen of them |
| Memory | A huge numbered array of bytes. Slower than registers |
| Address | The number of a slot in that array |
| Instruction pointer (RIP) | The register holding the address of what runs next |
| Stack | Scratch area for local variables and return addresses. Grows downward |
| Stack pointer (RSP) | The register pointing at the top of the stack |
| Flag | A single on/off bit set as a side effect of arithmetic |
| Opcode | The number that identifies an instruction |
| Assembly | The human-readable text form of those numbers |
| Disassembler | Turns bytes back into assembly text |
| Decompiler | Goes further and guesses the original C |
| Little-endian | Multi-byte numbers stored smallest-byte-first |
| Calling convention | The agreed rule about which registers hold arguments |

## Seven things to remember

1. Memory is a notebook with numbered lines. RIP holds the line number of what runs next.
2. Fetch, decode, execute, advance RIP. Forever. There is no step five.
3. Registers are the few variables you get, and `rax`/`eax`/`ax`/`al` are one register through four windows.
4. Memory is a giant array, and `[base + index*scale + offset]` is just `array[i]`.
5. The stack grows downward. `push` lowers RSP, `pop` raises it, and `pop` erases nothing.
6. `cmp` sets a flag, the branch reads it, `call` leaves a breadcrumb, `ret` follows it home.
7. It is all just numbers. Assembly is the disassembler being kind to you.

And the line that connects this to everything else:

**Exploitation is putting a value you chose into RIP. Everything else is plumbing.**

## Takeaways

A CPU is genuinely simple. Move data, do arithmetic, set flags, change RIP. The complexity of software is emergent, not built in.

The hard part of assembly is vocabulary, not concepts. You already understood variables, arrays, `if`, and function calls. This is those exact ideas with the training wheels off.

`call` and `ret` storing a return address in writable memory is the original sin that makes stack overflows possible. Every stack mitigation ever shipped patches over that one decision.

Calling conventions are agreements, not hardware. Linux and Windows disagree, and knowing which one you are looking at changes how you read a function.

What is on this page has not changed since the 1970s and will not change in your career. Only the instruction set will.

---

Image: [80486DX2 die shot](https://commons.wikimedia.org/wiki/File:80486DX2_200x.png) by Wikimedia user Uberpenguin, with Matt Gibbs, [CC BY-SA 2.5](https://creativecommons.org/licenses/by-sa/2.5/). Cropped and resized.
