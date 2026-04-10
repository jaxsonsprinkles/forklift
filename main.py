from github import Github
from github import Auth
from textual import on
from textual.app import App, ComposeResult
from textual.message import Message
from textual.widgets import Input, Label, SelectionList, Button, Header, DataTable
from textual.widgets.selection_list import Selection
from textual.containers import Horizontal, Container, VerticalGroup, Center
from rich.text import Text
import keyring


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
        if not self.access_token:
            yield Welcome()
        else:
            self.search_results = self.search(self.page) or []
            yield Header()
            with Horizontal():
                if self.search_results:
                    selections = [Selection(repo.full_name, repo.id)
                                  for repo in self.search_results]
                    yield Container(
                        SelectionList[int](*selections),
                        Horizontal(
                            Button("Submit", variant="primary", id="submit"),
                            Button("Load more", variant="warning",
                                   id="load-more"),
                        ),
                        id="select",
                    )
                else:
                    yield Label("No repositories found for this query.")
                with Container(id="queue"):
                    yield DataTable()
                    self.post_message(self.DataTableCreated())
                    yield Button("Start", variant="success")

    def _update_queue(self) -> None:
        table = self.query_one(DataTable)
        table.clear()
        table.add_rows((repo.full_name, Text("waiting", style="red"))
                       for repo in self.queued_repos)

    def on_mount(self) -> None:
        self.title = "Forklift"
        self.access_token = keyring.get_password("forklift", "access_token")
        if self.access_token:
            self.g = Github(auth=Auth.Token(self.access_token))
            self.refresh(recompose=True)

    def search(self, page) -> any:

        repos = self.g.search_repositories(
            "language:python good-first-issues:>3 stars:>500")

        if repos.totalCount > 0:
            return repos[((page-1)*20):(page*20)]
        else:
            return None

    @on(Welcome.InputSubmit)
    def on_input_submitted(self, event: Welcome.InputSubmit) -> None:
        token = event.value

        keyring.set_password("forklift", "access_token", token)
        self.access_token = token
        self.g = Github(auth=Auth.Token(token))
        self.refresh(recompose=True)

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
        self.search_results = self.search(self.page)
        self.refresh(recompose=True)

    @on(DataTableCreated)
    def on_datatable_created(self):
        table = self.query_one(DataTable)
        table.add_columns(*("name", "status"))


if __name__ == "__main__":
    app = Forklift()
    app.run()
