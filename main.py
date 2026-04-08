from github import Github
from github import Auth
from textual import on
from textual.app import App, ComposeResult
from textual.widgets import Input, Label, SelectionList, Button
from textual.widgets.selection_list import Selection
from textual.containers import Horizontal, Container
import keyring

class Forklift(App):
    CSS_PATH = "styles.tcss"

    access_token : str | None = None
    g : Github | None = None
    selected_repos: list | None = None
    def compose(self) -> ComposeResult:
        if not self.access_token:
            yield Label("Enter your access token (https://github.com/settings/tokens)")
            yield Input()
        else:
            search = self.search()
            with Horizontal():
                if search is not None:
                    selections = [Selection(repo.full_name, repo.id) for repo in search]
                    yield Container(
                        SelectionList[str](*selections),
                        Button("Submit", variant="primary"), id="select"
                    )
                else: 
                    yield Label("No repositories found for this query.")
                yield Label("Current Queue")
                
            

    
    
    def on_mount(self) -> None:
        self.access_token = keyring.get_password("forklift", "access_token")
        if self.access_token:
            self.g = Github(auth=Auth.Token(self.access_token))
            self.refresh(recompose=True)
            
    
    def search(self) -> any:
        
        repos = self.g.search_repositories("language:python good-first-issues:>3 stars:>500")
        
        if repos.totalCount > 0:
            return repos[:20]
        else:
            return None
    
    
    @on(Input.Submitted)
    def on_input_submitted(self, event: Input.Submitted) -> None:
        token = event.value.strip()
        if not token:
            return

        keyring.set_password("forklift", "access_token", token)
        self.access_token = token
        self.g = Github(auth=Auth.Token(token))
        self.refresh(recompose=True)


    @on(SelectionList.SelectedChanged)
    def updated_selected(self) -> None:
        self.selected_repos = list(self.query_one(SelectionList).selected)
        
        


if __name__ == "__main__":
    app = Forklift()
    app.run()





