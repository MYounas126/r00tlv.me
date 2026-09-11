---
title: "Four real CVEs in a 12-line C program"
date: 2026-09-18T01:00:00+05:00
categories: ["Notes"]
tags: ["c", "fundamentals", "appsec", "injection", "reverse-engineering"]
description: "Hello world with an argument has four named vulnerability classes in it, including a twelve-year-old local root on every mainstream Linux distribution."
summary: "Hello world with an argument has four named vulnerability classes in it, including a twelve-year-old local root on every mainstream Linux distribution."
cover:
  image: "/img/posts/re/hello-world.webp"
  alt: "Brian Kernighan's handwritten hello world program, framed and signed"
  hiddenInSingle: true
ShowToc: true
TocOpen: false
---

This is the program everyone writes first, with one argument added:

```c
#include <stdio.h>

int main(int argc, char *argv[])
{
    if (argc == 2) {
        printf("Hello %s!\n", argv[1]);
        return 0;
    }
    printf("Usage: %s <name>\n", argv[0]);
    return 1;
}
```

That is twelve lines of code, and sitting inside it are four real, named and patched vulnerability classes. One of them is a local root exploit which lived on inside a SUID binary on practically every mainstream Linux distribution for twelve years.

None of what follows is hypothetical.

## First, picture argv properly

Most of the confusion in this area comes from never having looked at `argv` concretely, so let us do that first:

```console
$ ./hello "John Doe" extra
```

The shell splits on spaces, keeps quoted text together, and hands the pieces over:

```
argc = 3

argv ->  [0] ----> "./hello"
         [1] ----> "John Doe"
         [2] ----> "extra"
         [3] ----> NULL
```

There are three things here which are worth fixing firmly in mind.

`argv[0]` holds the program name, so while counting begins at 0, the useful arguments begin at 1. `argc` will always be one more than the number of real arguments. And the quotes are consumed by the **shell** and not by your program, so `"John Doe"` arrives as a single argument containing a space, with the quote characters already removed.

You can think of `argv` as a numbered row of lockers, where locker 0 holds the program's own name badge and everything you passed in begins at locker 1. There is an empty locker at the end of the row so that the program knows where to stop.

Two of the four bugs below concern that first locker, and a third concerns who filled the lockers in the first place.

## 1. printf(argv[1]) and CWE-134

The program above correctly writes `printf("Hello %s!\n", argv[1])`. Now consider the shortcut which a tired developer will reach for:

```c
printf(argv[1]);              /* looks the same. is catastrophic. */
```

The first argument to `printf` is a **format string**, and the user is now in control of it. Feed it some specifiers and `printf` will obey them quite happily:

<img src="/img/posts/re/c-01-format-string.svg" alt="Comparing printf with a constant format string against printf where the user controls it, with each specifier consuming a stack value" width="820" height="420" loading="lazy" decoding="async" style="max-width:100%;height:auto;aspect-ratio:820/420">

| Input | What happens |
| :--- | :--- |
| `%x %x %x %x` | leaks values off the stack, in hex |
| `%s` | treats a stack value as a pointer and dumps whatever it points at, often crashing |
| `%p` | leaks raw pointers, defeating ASLR |
| `%n` | **writes** the number of characters printed so far to a pointed-at address |

The one which really matters here is `%n`, since it turns an information leak into an arbitrary write, and an arbitrary write is usually where the story ends. That is the reason `printf` appears in exploitation courses at all.

What is worth taking away from this is that **it is the very same bug as XSS and SQL injection**. Data has been mixed into a string which something else later on interprets as instructions. HTML interprets, SQL interprets, and `printf` interprets too. The fix has an identical shape in every case, which is to keep the template constant and pass the data along separately.

```c
printf("%s", user);    /* data is data */
printf(user);          /* data is now instructions */
```

That pair of lines is to `printf` what a parameterised query is to string-concatenated SQL.

Modern toolchains do put up a fight against this. GCC and Clang emit `-Wformat-security`, distributions build using `-Werror=format-security`, and `_FORTIFY_SOURCE` blocks `%n` whenever the format string happens to live in writable memory. The bug class has not gone away though. It has simply moved into older code, into embedded firmware, and into anywhere those flags are switched off.

## 2. argc == 2 and PwnKit

Every C programmer simply assumes that `argv[0]` exists. That is an assumption and not a guarantee.

The `execve` syscall allows a caller to launch a program with an empty argument list, which means `argc` can be **0** and `argv[0]` can be `NULL`.

<img src="/img/posts/re/c-02-pwnkit-argv-envp.svg" alt="With argc zero the argv array is empty, so indexing argv one reads past its NULL terminator into the adjacent environment array" width="820" height="400" loading="lazy" decoding="async" style="max-width:100%;height:auto;aspect-ratio:820/400">

This is [CVE-2021-4034](https://nvd.nist.gov/vuln/detail/CVE-2021-4034), "PwnKit", disclosed by Qualys in January 2022 and sitting unnoticed in polkit's `pkexec` since 2009. `pkexec` indexed into `argv` without confirming there was anything there. Because `argv` and `envp` are laid out next to each other in process memory, reading past the end of `argv` walked straight into the environment variables.

So you had an attacker-controlled environment being treated as arguments inside a SUID root binary. The result was a reliable local root on practically every mainstream Linux distribution.

Now look again at:

```c
if (argc == 2) {
```

That single comparison is the whole subject of a twelve-year-old critical CVE. It is not merely an analogy for it, it is the same class of bug.

The defensive habit required is a small one. Check `argc` before you go anywhere near `argv`, and never assume that `argv[0]` is non-NULL in anything privileged.

## 3. argv[0] is attacker-controlled too

The usage line prints `argv[0]`, which everybody describes as "your program name". To put it more accurately, **`argv[0]` is whatever the caller said that it was**, since `execve` allows the caller to set it to absolutely any string.

There are three consequences of this which you should know about:

Error and usage messages which echo `argv[0]` will faithfully print out an attacker's text. On its own that is a small matter, but it becomes a useful primitive once chained with something which logs or renders those messages.

Malware routinely sets `argv[0]` to something innocuous so it blends into `ps` output.

Some programs deliberately change their behaviour depending on `argv[0]`. Busybox does just this, as do the `gzip`/`gunzip` style multi-call binaries. If a privileged program branches on `argv[0]`, then the caller is in control of that branch.

## 4. The quoting boundary

The escaping demonstration which everybody runs at some point is really a security lesson in disguise:

```console
$ ./hello $USER        # shell expands first, program receives "younas"
$ ./hello \$USER       # backslash disables the meaning, program receives "$USER"
$ ./hello '$USER'      # single quotes do the same for the whole string
```

**The shell reads your command line before your program even exists.** The characters `$`, backtick, `*`, `;`, `|`, `&`, `(`, `)`, `<`, `>` and newline all carry meaning for it.

That is the entire mechanism behind command injection. A web application builds up a shell command out of user input, the shell then interprets the metacharacters, and the user's data becomes the server's instructions. The fix has the same shape once again, which is not to hand a string to a shell at all. Pass an argument array directly to `execve`, which in Python means `subprocess.run([...], shell=False)`.

I ran into the same principle from the other direction while working on [the Acode XSS](/posts/acode-cross-app-scripting-how-i-found-it/). My payload kept breaking, and the reason was that an unquoted HTML attribute is terminated by `>`, so an arrow function `f => ...` closed the tag early. Different interpreter, identical rule: **what the surrounding container treats as special decides what your data is allowed to be.**

Once you learn to ask "who is going to parse this string, and what is special to them?", a large part of injection stops being surprising at all.

## The compile flags that catch some of this

These are worth committing to muscle memory, since two of the four issues above get caught at build time:

```console
$ gcc -Wall -Wextra -Wformat-security -Werror=format-security \
      -D_FORTIFY_SOURCE=2 -fstack-protector-strong \
      -Wl,-z,relro,-z,now -pie hello.c -o hello
```

`-Wformat-security` will catch item 1. Nothing in that line catches items 2 to 4, because those are assumptions in the logic rather than mistakes a pattern can match against. That asymmetry is worth dwelling on, since a compiler is able to flag a wrong shape but it cannot flag a wrong belief about who controls your inputs.

## What this is actually teaching

The reason for looking this closely at hello world is that **the whole of injection comes down to a single idea**, and that idea is far easier to see in twelve lines than it is inside a framework.

A string crosses a boundary, and on the other side of that boundary something parses it. If the parser can be persuaded that some part of your data is structure rather than content, then you have an injection, and the name it ends up with depends purely on which parser was involved. `printf` gives you CWE-134. A browser gives you XSS. A database gives you SQLi. A shell gives you command injection. An HTML attribute gives you the bug I spent a fortnight on.

The other half of the lesson concerns trust. Three of the four bugs here arise from assuming something about the process which launched you, namely that `argv[0]` exists, that it holds your real name, and that the shell handed over what the user actually typed. None of these are true. They are conveniences which hold right up to the moment somebody calls `execve` directly.

## Related

- [How a CPU actually works](/posts/how-a-cpu-actually-works/) is the layer below this, and explains why an arbitrary write ends the story
- [Cross-app scripting in Acode, part 3: fixing it](/posts/acode-cross-app-scripting-how-to-prevent-it/) is the same escaping problem in a WebView
- [CVE-2021-4034 (PwnKit)](https://nvd.nist.gov/vuln/detail/CVE-2021-4034)

---

Image: ["Hello World" handwritten by Brian Kernighan, 1978](https://commons.wikimedia.org/wiki/File:Hello_World_Brian_Kernighan_1978.jpg) by Brian Kernighan, [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/). Cropped and resized.
