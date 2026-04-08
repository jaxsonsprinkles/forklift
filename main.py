from github import Github
from github import Auth
from textual.app import App, ComposeResult
from textual.widgets import Input, Label


class MyApp(App):

    def compose(self) -> ComposeResult:
        yield Label("Enter your access token")
        yield Input()


if __name__ == "__main__":
    app = MyApp()
    app.run()


""" auth = Auth.Token()
g = Github(auth=auth)

repos = g.search_repositories("language:python stars:>500 good-first-issues:>3")
print(dir(repos[0])) """
