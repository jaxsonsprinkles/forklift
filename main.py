from github import Github
from github import Auth
from textual import on, work
from textual.app import App, ComposeResult
from textual.message import Message
from textual.widgets import Input, Label, SelectionList, Button, Header, DataTable
from textual.widgets.selection_list import Selection
from textual.containers import Horizontal, Container, VerticalGroup, Center
from rich.text import Text
from claude_agent_sdk import query, ClaudeAgentOptions
import keyring
import asyncio
from git import Repo



options = ClaudeAgentOptions(
    system_prompt=open("SYSTEM_PROMPT.md", "r", encoding="utf-8").read(),
    permission_mode="bypassPermissions",
    cwd="/forks"
)

def build_user_prompt(repo):
    prompt = f"""You have access to a forked GitHub repository located at:
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

        def __init__(self, value) -> None:
            super().__init__()
            self.value = value

    def compose(self) -> ComposeResult:
        yield Center(Label("""███████╗ ██████╗ ██████╗ ██╗  ██╗██╗     ██╗███████╗████████╗
██╔════╝██╔═══██╗██╔══██╗██║ ██╔╝██║     ██║██╔════╝╚══██╔══╝
█████╗  ██║   ██║██████╔╝█████╔╝ ██║     ██║█████╗     ██║   
██╔══╝  ██║   ██║██╔══██╗██╔═██╗ ██║     ██║██╔══╝     ██║   
██║     ╚██████╔╝██║  ██║██║  ██╗███████╗██║██║        ██║   
╚═╝      ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚═╝╚═╝        ╚═╝   
                                                             """))
        yield Label("Enter your access token (https://github.com/settings/tokens)")
        yield Input()

    @on(Input.Submitted)
    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.post_message(self.InputSubmit(event.value.strip()))

class Main(Horizontal):
    def compose(self) -> ComposeResult:

        with Container(id="select"):
            yield SelectionList[int]()
            with Horizontal():
                yield Button("Submit", variant="primary", id="submit")
                yield Button("Load more", variant="warning", id="load-more")
                        
            
        with Container(id="queue"):
            yield DataTable()
            yield Button("Start", variant="success", id="start")



class Forklift(App):
    CSS_PATH = "styles.tcss"

    access_token: str | None = None
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
            

    def on_mount(self) -> None:
        self.title = "Forklift"
        table = self.query_one(DataTable)
        table.add_columns("Repository", "Status")
        self.access_token = keyring.get_password("forklift", "access_token")
        if self.access_token:
            self._authenticate(self.access_token)
            

    def _authenticate(self, token) -> None:
        keyring.set_password("forklift", "access_token", token)
        self.access_token = token
        self.g = Github(auth=Auth.Token(token))
        self.query_one(Welcome).display = False
        self.query_one(Main).display = True
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
        
    def _update_queue(self) -> None:
        table = self.query_one(DataTable)
        for repo in self.queued_repos:
            try:
                table.add_row(*(repo.full_name, Text("waiting", style="yellow")), key=repo.id)
            except Exception:
                pass

    @on(Button.Pressed, "#start")
    @work
    async def _start(self):
        current_repo = self.queued_repos[0]
        Repo.clone_from("https://github.com/"+current_repo.full_name, f"./forks/{current_repo.full_name.replace('/', '_')}")
        async for message in query(prompt=build_user_prompt(current_repo), options=options):
            print(message)

            

    @on(Welcome.InputSubmit)
    def on_input_submitted(self, event: Welcome.InputSubmit) -> None:
        self._authenticate(event.value)

    @on(SelectionList.SelectedChanged)
    def updated_selected(self, event: SelectionList.SelectedChanged) -> None:
        self.selected_repo_ids = list(event.selection_list.selected)

    @on(Button.Pressed, "#submit")
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

    @on(Button.Pressed, "#load-more")
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
