# Rules

## Contents
- Heading rules
- Link rules
- Fence rules

## Heading rules

| level | allowed parents | max length | notes |
|---|---|---|---|
| h1 | none | 60 | exactly one per file |
| h2 | h1 | 70 | |
| h3 | h2 | 80 | |
| h4 | h3 | 80 | avoid |
| h5 | h4 | 80 | avoid |
| h6 | h5 | 80 | never |

## Link rules

| kind | check |
|---|---|
| relative | target exists |
| anchor | heading exists in target |
| absolute http | not checked |

## Fence rules

| rule | detail |
|---|---|
| language | every fence names a language |
| length | fences over 80 lines get a note |
