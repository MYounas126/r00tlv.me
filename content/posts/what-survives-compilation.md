---
title: "What survives compilation, and what does not"
date: 2026-09-25T01:00:00+05:00
categories: ["Notes"]
tags: ["reverse-engineering", "x86-64", "elf", "ghidra", "fundamentals"]
description: "Reversing starts where the compiler ends. Knowing which build stage discarded which information tells you what you can recover from a binary."
summary: "Reversing starts where the compiler ends. Knowing which build stage discarded which information tells you what you can recover from a binary."
cover:
  image: "/img/posts/re/elf-layout.webp"
  alt: "Diagram of the ELF file layout"
  hiddenInSingle: true
ShowToc: true
TocOpen: false
---

Reverse engineering means analysing software to work out what it does when you do not have the source for it. That definition is easy enough to say but it is a little misleading, since it makes the missing source sound like some kind of accident.

It is nothing of the sort. Every build **deliberately throws information away** at each stage, and the last stage usually throws away even more on purpose. Knowing which stage discarded what tells you what you can realistically hope to recover from the binary in front of you, and what is simply gone.

If registers, the stack and `call`/`ret` are still a bit unclear, then [How a CPU actually works](/posts/how-a-cpu-actually-works/) covers all of those with animations. This post is about the layer sitting above that, namely how source becomes an ELF and what remains of it by the time you open the file.

## The four stages

An ordinary `gcc hello.c -o hello` quietly runs four separate things:

```
Pre-processing -> Compilation -> Assembly -> Linking -> Executable
```

| Stage | Does | Notably does not | Output |
| :--- | :--- | :--- | :--- |
| Pre-processing | expands macros, pastes in `#include` files, strips comments. Pure text substitution | **no syntax checking at all** | expanded source |
| Compilation | syntax checks, turns high-level code into assembly | | `.s` assembly |
| Assembly | encodes each instruction as opcodes, emits relocation entries for the linker to fill | | `.o` object file |
| Linking | resolves the entry point, lays out memory regions, binds symbols | | executable |

<img src="/img/posts/re/re-01-compile-pipeline.svg" alt="The four compilation stages, with each piece of source information struck out as the stage that discards it runs" width="820" height="430" loading="lazy" decoding="async" style="max-width:100%;height:auto;aspect-ratio:820/430">

You can watch each of these stages on its own, which teaches you far more than reading about them ever will:

```console
$ gcc -E hello.c -o hello.i     # stop after pre-processing
$ gcc -S hello.c -o hello.s     # stop after compilation
$ gcc -c hello.c -o hello.o     # stop after assembly
$ gcc hello.c -o hello          # all four
```

Do open `hello.i` at least once. A file of twelve lines turns into hundreds of lines, because `#include <stdio.h>` is a literal paste of text and not an import in the Python sense. Every comment you had written is already gone by this point, before the compiler has even looked at a single token.

That is the first thing the build discards and there is no getting it back. No decompiler is ever going to return a comment to you, for the simple reason that comments never survived stage one.

## What each stage costs you as a reverser

It is worth reading that table again as an attacker would, rather than as a developer.

**Pre-processing destroys comments along with macro structure.** A codebase full of macros reverses as though it had been written inline, because by the time the compiler sees it that is what it has become. There is no way to tell a `#define` apart from hand-written code.

**Compilation destroys variable names, types as written, and control-flow shape.** The compiler is quite free to unroll your loop, inline your function, reorder your statements and swap your `if` chain for a jump table, so long as the observable behaviour comes out the same. What you get back is equivalent in behaviour but not identical in structure.

**Assembly is the one lossless-ish step.** Assembly text maps almost one-to-one onto opcodes, and `objdump` reverses it cleanly:

```console
$ objdump -d --no-show-raw-insn -M intel hello.o
```

This is the reason disassembly is reliable while decompilation remains guesswork. Turning bytes back into mnemonics is merely a lookup, whereas turning mnemonics back into C is a matter of inference.

**Linking is where the deliberate stripping happens**, and it is the stage you actually fight.

## The symbol tables, and which one you get

An ELF carries two symbol tables at most, and the difference between the two accounts for most of the reason why one binary is pleasant to reverse while another is thoroughly miserable.

| Table | Contents | Present in a stripped release build? |
| :--- | :--- | :--- |
| `.symtab` | debugging and labelling symbols: function names, local symbols. The useful one | usually **no** |
| `.dynsym` | symbols needed for dynamic linking | **yes**, the loader needs it |

<img src="/img/posts/re/re-02-strip-symbols.svg" alt="strip removes the local symbol table while the dynamic symbols for imported functions remain" width="820" height="380" loading="lazy" decoding="async" style="max-width:100%;height:auto;aspect-ratio:820/380">

Removing `.symtab` is a deliberate anti-RE measure, and it is one `strip` away:

```console
$ nm hello | head                    # function names, readable
$ strip hello
$ nm hello
nm: hello: no symbols
$ nm -D hello | head                 # .dynsym survives: printf, __libc_start_main
```

The consequence here is quite specific and worth stating plainly. In a stripped binary you lose the names of the program's **own** functions, while retaining the names of everything it **imports** from shared libraries. So although you cannot see `validate_licence`, you can still see that it goes on to call `strcmp`, `open`, `ptrace` and `getenv`.

This asymmetry is your foothold. Cross-references from the imported functions are how one navigates a stripped binary, so if you find every call site of `strcmp` then you have found every place where the program compares strings, and in a crackme that is usually where the answer is hiding.

```console
$ readelf -h hello         # ELF header: class, endianness, entry point
$ readelf -S hello         # sections: .text, .data, .rodata, .symtab if present
$ readelf -l hello         # segments: what the loader maps and with what permissions
$ readelf -d hello         # dynamic section: needed libraries, RPATH
```

`.rodata` deserves a mention here because beginners tend to overlook it. String literals live in that section, they do not get stripped, and running `strings -a -t x` over a binary will often hand you the error messages, format strings and file paths which tell you what the program is meant for before you have read even one instruction.

## Formats, briefly

| Format | Platform |
| :--- | :--- |
| ELF | Linux |
| PE | Windows |
| Mach-O | macOS |
| COFF | older and embedded toolchains |

The concepts do transfer across. ELF sections and segments have their PE equivalents, symbol stripping works along the same lines, and the reason to learn one format properly instead of three of them loosely is that the second one turns out to be mostly a translation exercise.

## One real architectural difference you should know about

At first glance `eip` versus `rip` looks like nothing more than a naming convention with a larger number attached to it. That is not the case, and the difference turns up constantly in modern disassembly.

| | EIP (32-bit) | RIP (64-bit) |
| :--- | :--- | :--- |
| Size | 32 bits | 64 bits |
| Addressable | 4 GB | 16 EB |
| RIP-relative addressing | **no** | **yes** |

RIP-relative addressing means an instruction can reference memory relative to *its own address*:

```asm
mov rax, [rip + 0x200]
```

The 32-bit `eip` has no equivalent for this. It is what makes position-independent code practical, which in turn is what makes ASLR practical, and it is the reason 64-bit disassembly is full of `[rip + ...]` in places where 32-bit code would have had an absolute address baked into it.

In practical terms, when you come across `[rip + 0x2e04]` in a listing and want to know what it is actually pointing at, the address gets computed from the address of the *next* instruction and not the current one. Being off by one instruction length here is a very common early mistake.

## Where Ghidra fits

Ghidra is an open-source reverse engineering framework which was written by the NSA and released publicly in March 2019. It gives you a disassembler along with a decompiler, it is free, and it supports a broad range of architectures.

The workflow has remained stable since its release. You create a new project, import the binary, let auto-analysis run and then work in the CodeBrowser. Auto-analysis finds the entry point, disassembles, labels what functions it can, and resolves cross-references. On a stripped binary those labels will be `FUN_00401136` rather than names, which is the `.symtab` loss from earlier showing up in your tooling.

The part you really need to understand here is **P-Code**.

Ghidra does not keep a separate decompiler for each architecture. Instead it lifts machine code up into P-Code, an intermediate language which is shared across every processor it supports, and the decompiler then works on that. A specification language called SLEIGH describes how a given machine's instructions translate into P-Code.

That one design decision is why adding a new processor to Ghidra means writing a SLEIGH module rather than writing an entire decompiler. It is also why the decompiler output can occasionally look a bit odd in ways which have nothing to do with your binary, since what you are reading is C reconstructed from an intermediate representation, two translations removed from the actual bytes.

This is the same caution that applies everywhere else in this post. **The decompiler gives you a hypothesis while the disassembly is the evidence.** Whenever the two disagree, the bytes win.

## The short version

Reversing begins at machine code because machine code is the only artefact which is guaranteed to be there. Source, comments and symbol names are all optional, and the latter two are routinely removed quite deliberately.

Comments die at pre-processing and they never come back. Names and control-flow shape die at compilation, after which a decompiler can only guess at them. `.symtab` dies when `strip` runs, and that is the loss you really feel, although `.dynsym` and `.rodata` do survive and are usually enough to get your bearings.

Everything upstream of the bytes is a convenience which the build was perfectly free to throw away. Learning which convenience went where is most of what turns a stripped binary from something intimidating into something workable.

## Related

- [How a CPU actually works](/posts/how-a-cpu-actually-works/) covers registers, the stack and control flow, with animations
- [Four real CVEs in a 12-line C program](/posts/four-cves-in-twelve-lines-of-c/) is the source side of this pipeline

---

Image: [ELF layout diagram](https://commons.wikimedia.org/wiki/File:Elf-layout--en.svg) by Surueña, [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/). Cropped and resized.
