from pathlib import Path

import nox

nox.options.sessions = ["test", "coverage", "mypy"]  # "docs"]
nox.options.reuse_existing_virtualenvs = True


@nox.session(python="python3.10")
def coverage(session):
    session.run_always("poetry", "install", "--with=dev", external=True)
    session.env["TOP"] = str(Path(__file__).parent)
    try:
        session.run("coverage", "combine")
    except:
        pass
    session.run("coverage", "html")
    session.run("coverage", "report", "--fail-under", "100")
    session.run("coverage", "erase")


@nox.session(python="python3.10")
def mypy(session):
    session.install("poetry")
    session.run("poetry", "install", "--with=dev")
    session.run("mypy", "inline_snapshot", "tests")


@nox.session(python=["3.7", "3.8", "3.9", "3.10", "3.11"])
def test(session):
    session.run_always("poetry", "install", "--with=dev", external=True)
    session.env["COVERAGE_PROCESS_START"] = str(
        Path(__file__).parent / "pyproject.toml"
    )
    session.env["TOP"] = str(Path(__file__).parent)
    session.run(
        "pytest", "--doctest-modules", "inline_snapshot", "tests", *session.posargs
    )


@nox.session(python="python3.10")
def docs(session):
    session.install("poetry")
    session.run("poetry", "install", "--with=doc")
    session.run("mkdocs", "build", *session.posargs)


@nox.session(python="python3.10")
def mutmut(session):
    session.install("poetry")
    session.run("poetry", "install", "--with=dev")

    coverage = False

    if coverage:
        session.run("coverage", "erase")

        session.env["COVERAGE_PROCESS_START"] = str(
            Path(__file__).parent / "pyproject.toml"
        )
        session.env["TOP"] = str(Path(__file__).parent)
        session.run("pytest", "--doctest-modules", "inline_snapshot", "tests")
        session.run("coverage", "combine")

    session.run("mutmut", "run", *session.posargs)

    if coverage:
        session.run("coverage", "erase")
