# Slavs and an Ottoman

A hackathon project repository.

## About

This repository is the starting point for **Slavs and an Ottoman**. The project brief, intended audience, and planned features have not yet been recorded here; add them as the team defines the direction during the hackathon.

## Project status

The repository currently contains its project setup and this README. No application code or runnable prototype has been added yet.

## Getting started

There is no application to run yet. Once the team chooses a stack, document the prerequisites and setup steps here. At minimum, include:

1. Required tools and versions
2. Installation steps
3. The command to start the project
4. Any environment variables or services needed

## Team and contributions

Add team members, roles, and contribution guidance here. During the hackathon, keep this README updated with the project idea, implemented features, and instructions for trying the latest build.

## Agent session tracking

This repository uses [Entire](https://entire.io/) to save coding-agent session context alongside Git history. Contributors using Codex can install and enable the Entire CLI from the repository:

```sh
curl -fsSL https://entire.io/install.sh | bash
entire enable
```

Verify the setup with:

```sh
entire status
entire doctor
```

After Codex makes a real file change and that change is committed, Entire should push a checkpoint ref. Review the repository's hooks with `/hooks` before trusting them.
