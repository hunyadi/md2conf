---
title: "Admonitions and alerts"
---

Run the following command to synchronize this page:

```sh
python -m md2conf --use-panel sample/panel.md
```

## Admonitions

!!! info
    This is an information panel.

!!! info "Optional explicit title"
    This is an information panel with an explicit title.

    This is the second paragraph with a [link](https://example.com/).

!!! tip "Tip of the day"
    This is a structured macro panel showing a tip.

!!! note "A note"
    This is a structured macro panel showing a note.

!!! warning "A warning message"
    This is a structured macro panel showing a warning.

!!! attention
    This is a structured macro panel defined in rST syntax.

!!! caution
    This is a structured macro panel defined in rST syntax.

!!! danger
    This is a structured macro panel defined in rST syntax.

!!! error
    This is a structured macro panel defined in rST syntax.

!!! hint
    This is a structured macro panel defined in rST syntax.

!!! important
    This is a structured macro panel defined in rST syntax.

## GitHub alerts

Note:

> [!NOTE]
> Useful information that users should know, even when skimming content.

Tip:

> [!TIP]
> Helpful advice for doing things better or more easily.

Important:

> [!IMPORTANT]
> Key information users need to know to achieve their goal.

Warning:

> [!WARNING]
> Urgent info that needs immediate user attention to avoid problems.

Caution:

> [!CAUTION]
> Advises about risks or negative outcomes of certain actions.

## GitLab alerts

Flag:

> FLAG:
> The availability of this feature is controlled by a feature flag.
> For more information, see the history.
> This feature is available for testing, but not ready for production use.

Note:

> NOTE:
> This is something to note.

Warning:

> WARNING:
> This is something to be warned about.

Disclaimer:

> DISCLAIMER:
> This page contains information related to upcoming products, features, and functionality.
> It is important to note that the information presented is for informational purposes only.
> Please do not rely on this information for purchasing or planning purposes.
