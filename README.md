# r00tlv.me

Source for [r00tlv.me](https://r00tlv.me): writeups on web, mobile and
container security by Muhammad Younas.

Hugo + [PaperMod](https://github.com/adityatelange/hugo-PaperMod), deployed to
Cloudflare Pages.

```bash
git clone --recurse-submodules <repo>
hugo server          # http://localhost:1313
hugo --gc --minify   # production build into ./public
```

New post:

```bash
hugo new content posts/slug.md --kind htb        # or: research, notes
```

See [SETUP.md](SETUP.md) for deployment, DNS and the writing workflow.
