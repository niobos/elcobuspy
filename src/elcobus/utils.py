import os


def list_modules(path: str, recurse: bool=True):
    modules = []
    for file in os.listdir(path):
        if file.startswith('_'): continue

        full_path = os.path.join(path, file)
        if os.path.isdir(full_path) and \
                os.path.exists(os.path.join(full_path, '__init__.py')):
            # this is a package
            if recurse:
                submodules = list_modules(full_path)
                modules.extend(["{}.{}".format(file, m) for m in submodules])
        elif file.endswith('.py'):
            modules.append(file[:-3])
    return modules
