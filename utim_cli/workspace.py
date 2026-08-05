import os

class WorkspaceManager:
    def __init__(self, root_dir="."):
        self.root_dir = root_dir

    def list_files(self):
        file_tree = []
        for root, dirs, files in os.walk(self.root_dir):
            if ".git" in dirs:
                dirs.remove(".git")
            for file in files:
                file_tree.append(os.path.join(root, file))
        return file_tree

    def read_file(self, file_path):
        full_path = os.path.join(self.root_dir, file_path)
        if os.path.exists(full_path):
            with open(full_path, "r") as f:
                return f.read()
        return None

    def write_file(self, file_path, content):
        full_path = os.path.join(self.root_dir, file_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w") as f:
            f.write(content)
        return True

    def get_context(self):
        """Build a context string summarizing the workspace."""
        files = self.list_files()
        return f"Current Workspace Files: {', '.join(files[:20])}" # Limit for context size
