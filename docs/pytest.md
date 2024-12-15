
inline-snapshot provides one pytest option with different flags (*create*,
*fix*,
*trim*,
*update*,
*short-report*,
*report*,
*disable*).


Snapshot comparisons return always `True` if you use one of the flags *create*, *fix* or *review*.
This is necessary because the whole test needs to be run to fix all snapshots like in this case:

``` python
from inline_snapshot import snapshot


def test_something():
    assert 1 == snapshot(5)
    assert 2 <= snapshot(5)
```

!!! note
    Every flag with the exception of *disable* and *short-report* disables the pytest assert-rewriting.



## --inline-snapshot=create,fix,trim,update

Approve the changes of the given [category](categories.md).
These flags can be combined with *report* and *review*.

``` python title="test_something.py"
from inline_snapshot import snapshot


def test_something():
    assert 1 == snapshot()
    assert 2 <= snapshot(5)
```

```bash exec="1" title="something" result="ansi"
set -e
cd $(mktemp -d)
export -n CI
export -n GITHUB_ACTIONS

export FORCE_COLOR=256
export COLUMNS=80

function run(){
    echo -en "\x1b[1;34m> "
    echo $@
    echo -en "\x1b[0m"
    $@
    echo
}

black -q - > test_something.py << EOF
from inline_snapshot import snapshot

def test_something():
    assert 1 == snapshot()
    assert 2 <= snapshot(5)
EOF

run pytest test_something.py --inline-snapshot=create,report
```


## --inline-snapshot=short-report

give a short report over which changes can be made to the snapshots

```bash exec="1" title="something" result="ansi"
cd $(mktemp -d)
export -n CI
export -n GITHUB_ACTIONS

export FORCE_COLOR=256
export COLUMNS=80

function run(){
    echo -en "\x1b[1;34m> "
    echo $@
    echo -en "\x1b[0m"
    python -m $@
    echo
}

black -q - > test_something.py << EOF
from inline_snapshot import snapshot

def test_something():
    assert 1 == snapshot()
    assert 2 <= snapshot(5)
EOF

run pytest test_something.py --inline-snapshot=short-report
```

!!! info
    short-report exists mainly to show that snapshots have changed with enabled pytest assert-rewriting.
    This option will be replaced with *report* when this restriction is lifted.

## --inline-snapshot=report

Shows a diff report over which changes can be made to the snapshots

```bash exec="1" title="something" result="ansi"
cd $(mktemp -d)
export -n CI
export -n GITHUB_ACTIONS

export FORCE_COLOR=256
export COLUMNS=80

function run(){
    echo -en "\x1b[1;34m> "
    echo $@
    echo -en "\x1b[0m"
    $@
    echo
}

black -q - > test_something.py << EOF
from inline_snapshot import snapshot

def test_something():
    assert 1 == snapshot()
    assert 2 <= snapshot(5)
EOF

run pytest test_something.py --inline-snapshot=report
```

## --inline-snapshot=review

Shows a diff report for each category and ask if you want to apply the changes

```bash exec="1" title="something" result="ansi"
set -e
cd $(mktemp -d)
export -n CI
export -n GITHUB_ACTIONS

export FORCE_COLOR=256
export COLUMNS=80

function run(){
    echo -en "\x1b[1;34m> "
    echo $@
    echo -en "\x1b[0m"
    $@
    echo
}

black -q - > test_something.py << EOF
from inline_snapshot import snapshot

def test_something():
    assert 1 == snapshot()
    assert 2 <= snapshot(5)
EOF

yes | run pytest test_something.py --inline-snapshot=review
```



## --inline-snapshot=disable

Disables all the snapshot logic. `snapshot(x)` will just return `x`.
This can be used if you think exclude that snapshot logic causes a problem in your tests, or if you want to speedup your CI.

!!! info "deprecation"
    This option was previously called `--inline-snapshot-disable`
