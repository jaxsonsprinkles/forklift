from github import Github
from github import Auth
from textual import on
from textual.app import App, ComposeResult
from textual.widgets import Input, Label, SelectionList
from textual.widgets.selection_list import Selection
import keyring

class Forklift(App):
    access_token : str | None = None
    g : Github | None = None
    
    def on_mount(self) -> None:
        self.access_token = keyring.get_password("forklift", "access_token")
        if self.access_token:
            self.g = Github(auth=Auth.Token(self.access_token))
            self.refresh(recompose=True)
    
    def search(self) -> any:
        print("hi")
        repos = self.g.search_repositories("language:python stars:>500 good-first-issues:>3")
        return repos[:10]
    
    def compose(self) -> ComposeResult:
        if not self.access_token:
            yield Label("Enter your access token (https://github.com/settings/tokens)")
            yield Input()
        else:
            selections = [Selection(repo.full_name, repo.id) for repo in self.search()]
            yield SelectionList[int](*selections) 
    
    @on(Input.Submitted)
    def on_input_submitted(self, event: Input.Submitted) -> None:
        token = event.value.strip()
        if not token:
            return

        keyring.set_password("forklift", "access_token", token)
        self.access_token = token
        self.g = Github(auth=Auth.Token(token))
        self.refresh(recompose=True)
        
        


if __name__ == "__main__":
    app = Forklift()
    app.run()





