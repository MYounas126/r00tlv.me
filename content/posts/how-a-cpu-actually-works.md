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

Every diagram on this page is animated, so watch the movement first and read the words afterwards. If some section feels difficult, the animation will usually explain it better than the paragraph does.

Please do not try to memorise the instructions, because nobody really does that. There is a plain-English glossary at the bottom for any word that sounds made up.

## The one picture

A computer is a notebook and a very fast, very stupid clerk.

The notebook is memory, and every line in it has a number. The clerk reads one line, does whatever it says, and then moves on to the next one. For rough work the clerk keeps a few sticky notes on the desk, and those are the registers. One of these notes is a special one, because it holds the number of the line to be read next, and that one is the instruction pointer.

That really is the entire machine. Everything after this is detail.

<img src="/img/posts/cpu/cpu-01-memory-is-paper.svg" alt="Memory as a numbered notebook, with an orange arrow marking the current line" width="820" height="440" loading="lazy" decoding="async" style="max-width:100%;height:auto;aspect-ratio:820/440">

Do watch the orange arrow, as it is not there for decoration. The arrow is the instruction pointer, and the address written next to it is the line number currently being held.

| Machine width | Name of that register |
| :--- | :--- |
| 16-bit | `IP` |
| 32-bit | `EIP` |
| 64-bit | `RIP` |

It is the same register in all three cases. `E` stands for extended and `R` for 64-bit, and you will come across all three forms in writeups.

## The loop which is the CPU, more or less

<img src="/img/posts/cpu/cpu-03-fetch-decode-execute.svg" alt="The fetch, decode, execute cycle with a highlight moving between stages" width="820" height="340" loading="lazy" decoding="async" style="max-width:100%;height:auto;aspect-ratio:820/340">

The CPU reads the line, works out what it means, carries it out and then moves along to the next one, and it repeats this a few billion times every second.

There is no fifth step hiding anywhere.

This single idea matters more than anything else on the page, for the simple reason that nothing happens on a computer unless RIP is pointing at it. The goal of exploitation therefore turns out to be quite a simple one:

**Make RIP point at something you chose.**

Buffer overflows, ROP, format strings and use-after-free are all just different roads leading to that same destination. It is worth keeping that sentence in mind for everything that follows.

## Thing 1 of 4: registers

Registers are the variables of the CPU. There are roughly sixteen useful ones, they are built into the chip itself, and they are the only place where arithmetic actually takes place.

<img src="/img/posts/cpu/cpu-02-registers-and-flags.svg" alt="Registers changing value as instructions execute, with the zero flag flipping at the end" width="820" height="430" loading="lazy" decoding="async" style="max-width:100%;height:auto;aspect-ratio:820/430">

Watch `EAX` change with each instruction, then watch the zero flag flip to 1 at the end.

| Instruction | Plain English |
| :--- | :--- |
| `mov eax, 5` | put 5 in EAX. `mov` means copy, the source is not emptied |
| `add eax, 3` | EAX = EAX + 3 |
| `sub eax, ebx` | EAX = EAX - EBX |

The answer always ends up in the left-hand operand, and this holds for nearly every instruction listed here.

### What the sixteen are for

There is no need to memorise this table. Have a look at it now and come back to it whenever you run into a name you do not recognise.

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

This particular point confuses almost everybody, which is why it has been given its own animation.

<img src="/img/posts/cpu/cpu-10-register-windows.svg" alt="rax, eax, ax and al shown as four windows onto the same eight bytes" width="820" height="400" loading="lazy" decoding="async" style="max-width:100%;height:auto;aspect-ratio:820/400">

`rax`, `eax`, `ax` and `al` are not four separate registers at all, but rather four windows looking onto the same eight bytes.

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

Whenever you are reading disassembly and some register has mysteriously changed, this is almost always the reason behind it.

### Flags

Every `add`, `sub` and `cmp` quietly sets a few flags as a side effect. The first one to understand is the zero flag, which turns on whenever the last answer worked out to 0. It is that single on/off bit which makes decision-making possible at all.

## Thing 2 of 4: memory

Sixteen variables will obviously not take you very far. In a game, the player position, the lives remaining, every coin and every enemy all live in memory, and they only visit a register when the CPU needs to work on them.

<img src="/img/posts/cpu/cpu-04-load-and-store.svg" alt="Load moving a value from memory into a register, and store moving it back" width="820" height="400" loading="lazy" decoding="async" style="max-width:100%;height:auto;aspect-ratio:820/400">

```asm
mov eax, [0x4005db]     ; LOAD  : memory  -> register
mov [0x4005e3], eax     ; STORE : register -> memory
```

The square brackets here mean the same thing they mean in Python. Where `my_list[5]` fetches element 5, `[0x4005db]` fetches whatever is sitting at address `0x4005db`. An address is really just a very large index, since memory itself is a very large array of bytes numbered from zero.

Memory is to assembly what the disk is to a Python program. You pull things out into variables, do something with them, and eventually put them back.

### The brackets can do maths, and that is just arrays

<img src="/img/posts/cpu/cpu-13-addressing-modes.svg" alt="Base plus index times scale plus offset resolving to a single address" width="820" height="420" loading="lazy" decoding="async" style="max-width:100%;height:auto;aspect-ratio:820/420">

When you come across something like `[rbx + rcx*4 + 8]`, there is no reason to panic. It is simply `array[i]` written out the long way.

| Part | Means |
| :--- | :--- |
| base (`rbx`) | where the array starts |
| index (`rcx`) | which element you want |
| scale (`4`) | how many bytes each element takes |
| offset (`8`) | a fixed extra step, for example skipping a header |

The scale is always 1, 2, 4 or 8, because that is the size of a `char`, `short`, `int` or pointer. The CPU does the whole multiply-and-add for free, inside one instruction.

### Why everyone obsesses over keeping things in registers

<img src="/img/posts/cpu/cpu-09-speed-hierarchy.svg" alt="The latency gap between registers, cache levels and main memory" width="820" height="400" loading="lazy" decoding="async" style="max-width:100%;height:auto;aspect-ratio:820/400">

Registers are effectively free, whereas main memory costs a couple of hundred cycles. This gap is the reason caches exist in the first place, and in the modern era it is also the reason timing leaks secrets. Spectre and Meltdown are built on the fact that a cache hit and a cache miss take measurably different amounts of time.

## Thing 3 of 4: the stack

<img src="/img/posts/cpu/cpu-05-stack-push-pop.svg" alt="Push lowering the stack pointer and writing a value, pop raising it and leaving the bytes behind" width="820" height="470" loading="lazy" decoding="async" style="max-width:100%;height:auto;aspect-ratio:820/470">

The stack grows downward, toward smaller addresses.

| Operation | What actually happens |
| :--- | :--- |
| `push 5` | RSP goes down by 8, then 5 is written at the new RSP |
| `pop eax` | the value at RSP is copied into EAX, then RSP goes up by 8 |

`RSP` always points at the top item. Think of a stack of plates: you only ever add or take from the top.

Now for the detail in that animation which most tutorials skip over. **`pop` does not erase anything.** If you look at the numbers that turn grey, they are still sitting there in memory, byte for byte. All that `pop` does is move RSP back up, so that the space is treated as free from then onwards.

That leftover data is a real and constantly exploited bug class. Uninitialised variables, where a function reads stack space it never wrote and gets the previous function's leftovers. Memory disclosure, where those leftovers get sent back to you and leak addresses, defeating ASLR. Heartbleed was this shape of bug: read more than was written, receive whatever happened to be lying there.

## Thing 4 of 4: control flow, which is only ever writing to RIP

A CPU that could only run from top to bottom would not be able to loop, branch or call a function. Certain instructions therefore change RIP directly, and that is all a jump really is.

```asm
jmp 0x401050        ; roughly: mov rip, 0x401050
```

### Making a decision

<img src="/img/posts/cpu/cpu-07-conditional-branch.svg" alt="The same code taking two different paths depending only on the zero flag" width="820" height="450" loading="lazy" decoding="async" style="max-width:100%;height:auto;aspect-ratio:820/450">

This is the same code run twice over. Only the flag is different, and yet the path taken changes completely.

The part that finally makes `je` click is this. If arithmetic is all you have, how would you check whether two numbers are equal? You subtract one from the other, and if the answer comes out as 0 then they were equal.

So `cmp eax, ebx` is really just a `sub` which throws the answer away and keeps only the flags. After that, `je`, meaning "jump if equal", actually means "jump if the zero flag is set". The name tells you the intention while the flag is the actual mechanism.

| Instruction | Jumps when |
| :--- | :--- |
| `je` / `jz` | the two were equal (zero flag set) |
| `jne` / `jnz` | they were not equal |
| `jg`, `jl` | greater than, less than (signed) |
| `ja`, `jb` | above, below (unsigned) |

Every `if`, `while` and `for` loop you have ever written comes down to this pair of instructions, one which sets a flag and another which reads it.

### Calling a function

A function may be called from twenty different places, so it cannot possibly hard-code the way back. The return path has to be stored somewhere, and the place it gets stored is the stack.

<img src="/img/posts/cpu/cpu-06-call-and-ret.svg" alt="call pushing a return address then jumping, ret popping it back into RIP" width="820" height="470" loading="lazy" decoding="async" style="max-width:100%;height:auto;aspect-ratio:820/470">

```
call  =  push (address of the next instruction)  +  jmp
ret   =  pop that address back into RIP
```

In short, `call` leaves behind a breadcrumb and `ret` follows it home, and there is nothing more to the mechanism than that.

Now have a look at that animation once more, this time from an attacker's point of view.

The return address is nothing more than data sitting in memory, and it sits right beside the buffers into which functions write your input. If you are able to write past the end of a buffer, you will reach that saved return address. Overwrite it, and when `ret` runs it will pop **your** value into RIP.

Recall the goal, which was to make RIP point at something of your choosing. `ret` will happily do this for you, because it has no way of telling your value apart from the one that `call` had saved. That, in a couple of sentences, is a stack buffer overflow.

Every mitigation you have heard of is defending this one moment. Stack canaries are there to detect the overwrite, ASLR hides the target, NX prevents your data from being runnable, and CFI checks that the destination is a legal one.

### How arguments get in and results get out

<img src="/img/posts/cpu/cpu-12-calling-convention.svg" alt="Arguments being placed in rdi, rsi, rdx before a call, and the result arriving in rax" width="820" height="430" loading="lazy" decoding="async" style="max-width:100%;height:auto;aspect-ratio:820/430">

There is no such thing as a parameter at this level. Arguments are simply agreed-upon registers which get filled in just before the `call` happens.

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

This ordering is known as a calling convention, and it is an agreement rather than any hardware rule. Linux and macOS follow the order given above, while Windows x64 follows a different one, namely `rcx`, `rdx`, `r8` and `r9`. The idea is the same, only the agreement differs.

This is also the reason a decompiler is able to label arguments in the first place, since it can see which registers a function reads before it has written to them.

## And none of it is text

<img src="/img/posts/cpu/cpu-08-assembly-is-just-numbers.svg" alt="The instruction mov eax, 5 shown as the bytes B8 05 00 00 00 in memory" width="820" height="430" loading="lazy" decoding="async" style="max-width:100%;height:auto;aspect-ratio:820/430">

The text `mov eax, 5` does not exist anywhere in memory. What exists in memory is `B8 05 00 00 00`.

`B8` is the opcode, meaning "load the next 4 bytes into EAX". `05 00 00 00` is the number, stored little-endian, smallest byte first, so it reads as `0x00000005`.

A disassembler converts those bytes back into text that you can read, which is a convenience for us rather than the underlying truth.

There are three consequences of this which matter a great deal later on:

**Patching a program means changing bytes.** Flip `74` (`je`) to `75` (`jne`) and you have inverted a licence check.

**x86 instructions are not of a fixed length.** They range anywhere from 1 to 15 bytes, so if you begin disassembling from a different offset you will end up with a completely different program which is still perfectly valid. This is how disassemblers can be fooled.

**Code and data are the same bytes.** Nothing marks a byte as an instruction. The CPU simply runs whatever RIP points at, which is why controlling RIP is so powerful, and why NX had to be invented to say "these bytes are data, refuse to run them".

## The whole instruction set you need right now

I mean that quite seriously. This table, along with the four ideas above, will take you a long way.

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
2. Fetch, decode, execute and advance RIP, on and on without stopping. There is no step five.
3. Registers are the few variables you get, and `rax`/`eax`/`ax`/`al` are one register through four windows.
4. Memory is a giant array, and `[base + index*scale + offset]` is just `array[i]`.
5. The stack grows downward. `push` lowers RSP, `pop` raises it, and `pop` erases nothing.
6. `cmp` sets a flag, the branch reads it, `call` leaves a breadcrumb, `ret` follows it home.
7. In the end it is all just numbers, and assembly is only the disassembler being kind to you.

And the line that connects this to everything else:

**Exploitation is putting a value you chose into RIP. Everything else is plumbing.**

## Takeaways

A CPU is a simple thing at heart. It moves data about, does arithmetic, sets flags and changes RIP. The complexity we see in software emerges from that, it is not built into the machine.

The difficult part of assembly is the vocabulary rather than the concepts. You already understood variables, arrays, `if` statements and function calls, and this is the same set of ideas with the training wheels taken off.

`call` and `ret` storing a return address in writable memory is the original sin that makes stack overflows possible. Every stack mitigation ever shipped patches over that one decision.

Calling conventions are agreements, not hardware. Linux and Windows disagree, and knowing which one you are looking at changes how you read a function.

Nothing on this page has changed since the 1970s and none of it will change during your career. Only the instruction set is going to change.

---

Image: [80486DX2 die shot](https://commons.wikimedia.org/wiki/File:80486DX2_200x.png) by Wikimedia user Uberpenguin, with Matt Gibbs, [CC BY-SA 2.5](https://creativecommons.org/licenses/by-sa/2.5/). Cropped and resized.
