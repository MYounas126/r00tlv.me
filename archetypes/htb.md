---
title: "HTB: {{ replace .Name "-" " " | title }}"
date: {{ .Date }}
draft: true
categories: ["HTB"]
tags: ["htb-linux", "htb-easy"]
description: ""
ShowToc: true
TocOpen: false
---

One paragraph: OS, difficulty, main technique. Two sentences max.

## Recon

```console
$ nmap -sC -sV -oA nmap/initial 10.10.11.XXX
```

One or two sentences on what stands out.

## Foothold

### Web

```console
$ ffuf -w wordlists/raft-medium-directories.txt -u http://HOST/FUZZ -mc 200,301,302
```

### Exploitation

```http
POST /path HTTP/1.1
Host: HOST
Content-Type: application/x-www-form-urlencoded

payload
```

### Shell

```console
$ nc -lnvp 9001
```

## User

### Priv esc

```console
$ linpeas.sh | tee linpeas.out
```

### The flag

```console
user@host:~$ cat /home/user/user.txt
```

## Root

### Priv esc

Real reasoning, not "I ran a tool."

### The flag

```console
root@host:~# cat /root/root.txt
```
