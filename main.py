from github import Github
from github import Auth
from textual import on, work
from textual.app import App, ComposeResult
from textual.message import Message
from textual.widgets import Input, Label, SelectionList, Link, Header, Footer, DataTable, RichLog
from textual.widgets.selection_list import Selection
from textual.containers import Horizontal, Container, VerticalGroup, Center, Grid
from textual.coordinate import Coordinate
from textual.validation import Length
from rich.text import Text
from claude_agent_sdk import query, ClaudeAgentOptions
import os
import asyncio
from git import Repo
from dotenv import load_dotenv, set_key

load_dotenv()

options = ClaudeAgentOptions(
    system_prompt=open("SYSTEM_PROMPT.md", "r", encoding="utf-8").read(),
    permission_mode="bypassPermissions",
    cwd="./forks"
)


def build_user_prompt(repo):
    return f"""You have access to a forked GitHub repository located at:
forks/{repo.full_name.replace("/", "_")}/
Repository: {repo.full_name}
Open issues: {[issue.title for issue in repo.get_issues(state='open')]}

Explore the repository yourself. Start with the root directory, then focus on
source files. Ignore anything in vendor/, dist/, build/, .github/, and any
auto-generated or lock files.

Find one improvement that fits the criteria in your instructions and produce
your JSON output."""


class Welcome(VerticalGroup):
    CSS_PATH = "styles.tcss"

    class InputSubmit(Message):

        def __init__(self, github_token, claude_token) -> None:
            super().__init__()
            self.github = github_token
            self.claude = claude_token

    def compose(self) -> ComposeResult:
        yield Center(Label("""███████╗ ██████╗ ██████╗ ██╗  ██╗██╗     ██╗███████╗████████╗
██╔════╝██╔═══██╗██╔══██╗██║ ██╔╝██║     ██║██╔════╝╚══██╔══╝
█████╗  ██║   ██║██████╔╝█████╔╝ ██║     ██║█████╗     ██║   
██╔══╝  ██║   ██║██╔══██╗██╔═██╗ ██║     ██║██╔══╝     ██║   
██║     ╚██████╔╝██║  ██║██║  ██╗███████╗██║██║        ██║   
╚═╝      ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚═╝╚═╝        ╚═╝   
                                                             """))
        yield Label("Enter your access token and Claude Code OAuth Token.")
        yield Link("Need help?", url="https://github.com/jaxsonsprinkles/forklift/README.md")
        # Numbers are arbitrary but there to prevent empty input submissions
        yield Input(password=True, placeholder="Github access token", id="github", validators=[Length(30, 200)])
        yield Input(password=True, placeholder="Claude token", id="claude", validators=[Length(50, 200)])

    def action_submit(self) -> None:
        github_input = self.query_one("#github", Input)
        claude_input = self.query_one("#claude", Input)

        if not github_input.validate(github_input.value.strip()).is_valid:
            github_input.focus()
            return

        if not claude_input.validate(claude_input.value.strip()).is_valid:
            claude_input.focus()
            return

        self.post_message(self.InputSubmit(
            github_input.value.strip(), claude_input.value.strip()))


class Main(Horizontal):
    BINDINGS = [
        ("l", "load_more", "Load more repos"),
        ("e", "start", "Start queue"),
        ("up", "select_previous", "Select previous"),
        ("down", "select_next", "Select next"),
    ]

    def compose(self) -> ComposeResult:

        with Grid():

            with Container(id="filters"):
                yield Label("Placeholder")

            with Container(id="select"):
                yield SelectionList[int]()

            with Container(id="queue"):
                yield DataTable()

            with Container(id="logs"):
                yield RichLog()

    def action_load_more(self) -> None:
        self.app.action_load_more()

    def action_start(self) -> None:
        self.app.action_start()

    def action_select_previous(self) -> None:
        self.app.action_select_previous()

    def action_select_next(self) -> None:
        self.app.action_select_next()


class Forklift(App):
    CSS_PATH = "styles.tcss"
    BINDINGS = [
        ("s", "submit", "Submit"),
        ("q", "quit", "Quit")
    ]

    access_token: str | None = None
    claude_token: str | None = None
    g: Github | None = None
    search_results: list = []
    selected_repo_ids: list[int] = []
    queued_repos: list = []
    page: int = 1

    class DataTableCreated(Message):

        def __init__(self) -> None:
            super().__init__()

    def compose(self) -> ComposeResult:
        yield Header()
        yield Welcome()

        main = Main()
        main.display = False
        yield main
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Forklift"
        table = self.query_one(DataTable)
        table.add_columns("Repository", "Status")
        self.query_one("#filters").border_title = "Filters"
        self.query_one("#select").border_title = "Repo select"
        self.query_one("#queue").border_title = "Queue"
        self.query_one("#logs").border_title = "Logs"
        self.access_token = os.getenv("GITHUB_ACCESS_TOKEN")
        self.claude_token = os.getenv("CLAUDE_CODE_OAUTH_TOKEN")
        if self.access_token and self.claude_token:
            self._authenticate(self.access_token, self.claude_token)

    def _authenticate(self, github, claude) -> None:
        set_key(".env", "GITHUB_ACCESS_TOKEN", github)
        self.access_token = github
        self.g = Github(auth=Auth.Token(github))
        set_key(".env", "CLAUDE_CODE_OAUTH_TOKEN", claude)
        self.claude_token = claude
        self.query_one(Welcome).display = False
        self.query_one(Main).display = True
        self.query_one(SelectionList).focus()
        self._load_repos()

    @work(thread=True)
    def _load_repos(self) -> None:
        repos = self._fetch_page(self.page)
        self.search_results = repos
        selections = [
            Selection(repo.full_name, repo.id) for repo in repos
        ]
        self.call_from_thread(self._set_selections, selections)

    def _set_selections(self, selections) -> None:
        selection_list = self.query_one(SelectionList)
        for s in selections:
            selection_list.add_option(s)

    def _fetch_page(self, page) -> list:
        repos = self.g.search_repositories(
            "language:python good-first-issues:>3 stars:>500")
        if repos.totalCount > 0:
            return repos[((page-1)*20):(page*20)]
        else:
            return []

    def action_submit(self) -> None:
        if self.query_one(Welcome).display:
            self.query_one(Welcome).action_submit()
            return

        self.on_submit_pressed()

    def action_load_more(self) -> None:
        if self.query_one(Welcome).display:
            return
        self.on_loadmore_pressed()

    def action_start(self) -> None:
        if self.query_one(Welcome).display:
            return
        self._start()

    def action_select_previous(self) -> None:
        if self.query_one(Welcome).display:
            return
        selection_list = self.query_one(SelectionList)
        selection_list.action_cursor_up()

    def action_select_next(self) -> None:
        if self.query_one(Welcome).display:
            return
        selection_list = self.query_one(SelectionList)
        selection_list.action_cursor_down()

    def _update_queue(self) -> None:
        table = self.query_one(DataTable)
        for repo in self.queued_repos:
            try:
                table.add_row(
                    *(repo.full_name, Text("Not started", style="red")), key=repo.id)
            except Exception:
                pass

    @work
    async def _start(self) -> None:
        if not self.queued_repos:
            return

        for i, repo in enumerate(self.queued_repos):
            log = self.query_one(RichLog)
            table = self.query_one(DataTable)
            table.update_cell_at(Coordinate(i, 1),
                                 Text("In progress", style="yellow"))
            log.write(
                Text(f"-----({repo.full_name})-----", style="bold purple"))
            log.write("Cloning repository...")
            await asyncio.to_thread(Repo.clone_from, "https://github.com/"+repo.full_name,
                                    f"./forks/{repo.full_name.replace('/', '_')}")
            log.write("Cloned")
            async for message in query(prompt=build_user_prompt(repo), options=options):
                log.write(Text(f"CLAUDE: {message}"))

    @on(Welcome.InputSubmit)
    def on_input_submitted(self, event: Welcome.InputSubmit) -> None:
        self._authenticate(event.github, event.claude)

    @on(SelectionList.SelectedChanged)
    def updated_selected(self, event: SelectionList.SelectedChanged) -> None:
        self.selected_repo_ids = list(event.selection_list.selected)

    def on_submit_pressed(self) -> None:
        selected_ids = set(self.selected_repo_ids)
        queued_ids = {repo.id for repo in self.queued_repos}

        new_repos = [
            repo
            for repo in self.search_results
            if repo.id in selected_ids and repo.id not in queued_ids
        ]

        if new_repos:
            self.queued_repos.extend(new_repos)
            self._update_queue()

    def on_loadmore_pressed(self) -> None:
        self.page += 1
        self._load_repos()

    @on(DataTableCreated)
    def on_datatable_created(self):
        table = self.query_one(DataTable)
        table.add_columns(*("name", "status"))


if __name__ == "__main__":
    app = Forklift()
    app.run()
