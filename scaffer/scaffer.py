#!python2
from __future__ import print_function
import os
import argp
import glob
import urllib
import json
import pprint
import itertools
import emitter

GITIGNORE = "https://raw.githubusercontent.com/github/gitignore/master/%s.gitignore"

RC_FILE = os.path.expanduser("~/.scaffer/scaffer.json")

def ensure_dir_for(pth):
    dname = os.path.dirname(pth)
    if not os.path.isdir(dname):
        os.makedirs(dname)


def emit_file(pth, cont, overwrite=False):
    print("- Emit", pth)
    ensure_dir_for(pth)
    if os.path.exists(pth) and not overwrite:
        print("Can't overwrite", pth)
        return
    open(pth,"wb").write(cont)

def fetch_url_to(fname, url):
    print("- Emit", fname, url)
    urllib.urlretrieve(url, fname)


def do_gitignore(args):
    """ Create gitignore file """
    if args.net:
        name = "VisualStudio"
    elif args.python:
        name = "Python"
    else:
        print("Must specify language! (--net, --python)")
        return

    fetch_url_to(".gitignore", GITIGNORE % name)


def do_barrel(arg):
    """ Create index.ts barrel in current directory """

    files = glob.glob("*.ts")
    lines = ['export * from "./%s";' % os.path.splitext(f)[0] for f in files ]

    emit_file("index.ts", "\n".join(lines))


def discover_files_in_parents(filenames, startdir):
    cur = startdir
    while 1:
        for fname in os.listdir(cur):
            if fname in filenames:
                fpath = os.path.join(cur, fname)
                yield fpath
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent

def get_key_from_json(fname, key):
    try:
        c = json.load(open(fname))
    except ValueError:
        return None
    return c.get(key)

def find_templates():
    files = list(discover_files_in_parents(['package.json', 'scaffer.json'], os.getcwd()))
    home_rc = os.path.expanduser("~/.scaffer/scaffer.json")
    if os.path.isfile(home_rc):
        files.append(home_rc)

    for f in files:
        dirs = get_key_from_json(f, "scaffer")
        if not dirs:
            continue
        rdir = os.path.dirname(f)
        for d in dirs:
            tdir = os.path.join(rdir,d)
            if not os.path.isdir(tdir):
                print("Warning! Missing:",tdir)
                continue

            templates = os.listdir(tdir)
            for t in templates:
                full = os.path.normpath(os.path.join(tdir,t))
                if os.path.isdir(full):
                    yield (t, full)

def run_scaffer_init(pth, vars, prefilled, target_dir):
    """ Will mutate prefilled! """
    print("Running", pth)
    cont=  open(pth).read()
    output_dict = {}
    ns = {
        "scaffer_in": {
            "target_dir": target_dir,
            "vars": vars,
            "prefilled": prefilled
        },
        # the populated vars should end up here
        "scaffer_out": output_dict
    }
    exec(cont,ns)
    print("Init populated:", ns["scaffer_out"])
    prefilled.update(output_dict)

def do_gen(arg):
    """ Generate complex template """
    tgt_dir = os.getcwd()
    ts = find_templates()
    if not arg.template:
        print("No template specified. Available templates:")
        for n, p in sorted(ts):
            print("%s\t%s" % (n,p))
        return

    if os.path.isdir(arg.template):
        to_gen = [(arg.template, arg.template)]
    else:
        to_gen = (t for t in ts if t[0] == arg.template)

    for template in to_gen:
        os.chdir(template[1])
        content = list(emitter.files_with_content("."))
        all_content = "".join(t[0] + "\n"+ t[1] for t in content)
        prefilled_vars = {
            k:v for (k,v) in (a.split("=", 1) for a in arg.v)
        }
        vars = emitter.discover_variables(all_content)
        if os.path.isfile("scaffer_init.py"):
            run_scaffer_init(os.path.abspath("scaffer_init.py"), vars, prefilled_vars, tgt_dir)

        unknown_prefilled = set(prefilled_vars.keys()).difference(vars)
        if unknown_prefilled:
            print("Warning! Unknown variables on command line:", ", ".join(unknown_prefilled))
        to_fill = vars.difference(set(prefilled_vars.keys()))
        filled = emitter.prompt_variables(to_fill) if to_fill else {}
        filled.update(prefilled_vars)
        renderings = emitter.var_renderings(filled)
        new_cont = emitter.rendered_content(content, renderings)
        for fname, content in new_cont:
            absname = os.path.normpath(os.path.join(tgt_dir, fname))
            emit_file(absname, content, arg.f)

def read_rc():
    if not os.path.isfile(RC_FILE):
        return {}
    return json.load(open(RC_FILE))

def write_rc(d):
    ensure_dir_for(RC_FILE)
    json.dump(d, open(RC_FILE, "w"), indent=2)



def do_add(arg):
    """ Add current directory to global templates directory """
    old = read_rc()
    olddirs = old.get("scaffer", [])
    olddirs.append(os.getcwd())
    old["scaffer"] = sorted(set(olddirs))
    write_rc(old)

def main():
    argp.init()

    argp.sub("barrel", do_barrel, help="Create index.tx for current directory")
    # gitignore
    gi = argp.sub("gitignore", do_gitignore, help="Create .gitignore file")
    gi.arg("--net", action="store_true")
    gi.arg("--python", action="store_true")

    # g
    gen = argp.sub("g", do_gen, help="Generate code from named template")
    gen.arg('-v', help="Give value to variable", nargs="+", default=[], metavar="variable=value")
    gen.arg('-f', help="Overwrite files if needed", action="store_true")
    gen.arg("template", help="Template to generate", nargs="?")

    argp.sub("add", do_add, help="Add current directory as template root in user global scaffer.json")

    argp.parse()

if __name__ == "__main__":
    main()