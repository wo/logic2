#!/usr/bin/python3
"""Create HTML version of textbook."""

import os
import re
import shutil
import subprocess
import argparse
import datetime
from bs4 import BeautifulSoup

tmp_path = "tmp"
html_path = "html"

tex4ht_config = r"""
\Preamble{xhtml}
\Configure{tableofcontents*}{chapter,section,subsection}
\begin{document}
\EndPreamble
"""


def main():
    """Create HTML version of textbook."""
    argparser = argparse.ArgumentParser(description="Create HTML version")
    argparser.add_argument('-f', '--fake', action='store_true', help="Use fake make4ht")
    argparser.add_argument('-v', '--verbose', action='store_true', help="Verbose output")
    args = argparser.parse_args()

    if not args.fake:
        prepare_paths()
        prepare_tex()
        make4ht(verbose=args.verbose)
        restore_css()
    save_or_restore_make4ht_output(restore=args.fake)

    rename_html_files()
    fix_toc_links()
    fix_html()
    create_index()
    check_links()


def prepare_paths():
    """Ensure tmp and html directories exist and tmp is empty."""
    try:
        shutil.rmtree(tmp_path)
    except FileNotFoundError:
        pass
    os.mkdir(tmp_path)
    if not os.path.exists(html_path):
        os.mkdir(html_path)
    # delete all html and svg files in html_path:
    # for f in os.listdir(html_path):
    #     if f.endswith('.html') or f.endswith('.svg'):
            # os.remove(html_path + '/' + f)
    # rename logic2.css in html_path so that we can restore it later:
    if os.path.exists(html_path + '/logic2.css'):
        print("Renaming logic2.css to _logic2.css")
        shutil.copyfile(html_path + '/logic2.css', html_path + '/_logic2.css')
    # create tex4ht configuration file:
    write_file(tmp_path + "/mytex4ht.cfg", tex4ht_config.strip())


def restore_css():
    """Restore customized logic2.css file that's overwritten by make4ht."""
    if os.path.exists(html_path + '/_logic2.css'):
        shutil.move(html_path + '/_logic2.css', html_path + '/logic2.css')


def prepare_tex():
    """Prepare the LaTeX files for processing."""
    shutil.copy('logic2.tex', tmp_path + '/logic2.tex')
    for chapter in tex_files(): 
        prep_chapter(chapter)
    prep_header_boxes()
    prep_xyling_sty()
    prep_logic2_cls()
    shutil.copy('KMcalc.sty', tmp_path)
    shutil.copy('doclicense-CC-by-nc-sa.pdf', tmp_path)
    shutil.copy('logic2book.css', tmp_path)


def tex_files():
    """Return list of chapter files."""
    pattern = re.compile(r'^\d\d-[^.]+\.tex$')
    chapters = [f for f in os.listdir('.') if pattern.match(f)]
    chapters.append('title.tex')
    chapters.append('answers.tex')
    return chapters


def html_files():
    """Return list of HTML files."""
    return [f for f in os.listdir(html_path) if f.endswith('.html')]


def prep_header_boxes():
    """Edit header-boxes.tex for conversion to HTML."""
    tex = read_file('header-boxes.tex')
    tex = re.sub('enforce breakable,', '%enforce breakable,', tex)
    tex = re.sub('breakable,', '%breakable,', tex)
    write_file(tmp_path + "/header-boxes.tex", tex)


def prep_xyling_sty():
    """Prepare xyling.sty for conversion to HTML."""
    sty = read_file("xyling.sty")
    sty = re.sub('\\\\newcommand{\\\\Link}\\[2\\]', '\\\\renewcommand{\\\\Link}[2]', sty)
    write_file(tmp_path + "/xyling.sty", sty)


def prep_logic2_cls():
    """Prepare logic2.cls for conversion to HTML."""
    cls = read_file("logic2.cls")
    cls = re.sub('\\\\usepackage{ifthen}', '\\\\usepackage{etoolbox}', cls)
    cls = re.sub('\\\\newcommand{\\\\wlabel}\\[2\\]{\\\\Kk\\[#1\\]\\{0\\}{\\\\ifthenelse { \\\\equal {#2} {} } {} {\\\\ensuremath{\\(#2\\)}}}}',
                  '\\\\newcommand{\\\\wlabel}[2]{\\\\Kk[#1]{0}{\\\\ifstrequal {#2} {} {} {\\\\ensuremath{(#2)}}}}', cls)
    write_file(tmp_path + "/logic2.cls", cls)


def prep_chapter(texfile):
    """Edit LaTeX chapter for conversion to HTML."""
    tex = read_file(texfile)
    tex = remove_noindent(tex)
    tex = fix_custom_commands(tex)
    tex = fix_gather(tex)
    tex = escape_labeled_items(tex)
    tex = escape_intext_links(tex)
    write_file(tmp_path + "/" + texfile, tex)


def remove_noindent(tex):
    r"""Remove \noindent commands that prevent rendering text as p."""
    return re.sub(r'\\noindent\s*%?', '', tex)


def fix_custom_commands(tex):
    """Fix custom commands that make4ht doesn't understand."""
    tex = re.sub(r'\\L', r'\\mathfrak{L}', tex)
    tex = re.sub(r'\\Cfr', r'\\mathfrak{C}', tex)
    tex = re.sub(r'\\Mfr', r'M', tex)
    tex = re.sub(r'\\t\{([^}]+)\}', r'\\langle \1 \\rangle', tex)
    tex = re.sub(r'\\notmodels', r'\\mathrel{|}\\joinrel\\not=', tex)
    tex = re.sub(r'\\principle\{([^}]+)\}\{([^}]+)\}', r'\\begin{equation}\\tag{\1}\2\\end{equation}', tex)
    tex = re.sub(r'\\begin{principles}', r'\\begin{enumerate}', tex)
    tex = re.sub(r'\\end{principles}', r'\\end{enumerate}', tex)
    tex = re.sub(r'\\pri\{([^}]+)\}\{(.+)\}', r'\\item[(\1)] $\2$', tex)
    tex = re.sub(r'\\pr\{([^}]+)\}', r'(\1)', tex)
    tex = re.sub(r'\\Kn', r'\\mathsf{K}', tex)
    tex = re.sub(r'\\Mi', r'\\mathsf{M}', tex)
    tex = re.sub(r'\\Bel', r'\\mathsf{B}', tex)
    tex = re.sub(r'\\EKn', r'\\mathsf{E}', tex)
    tex = re.sub(r'\\CKn', r'\\mathsf{C}', tex)
    tex = re.sub(r'\\tP', r'\\mathsf{P}', tex)
    tex = re.sub(r'\\tF', r'\\mathsf{F}', tex)
    tex = re.sub(r'\\tG', r'\\mathsf{G}', tex)
    tex = re.sub(r'\\tH', r'\\mathsf{H}', tex)
    tex = re.sub(r'\\tX', r'\\mathsf{X}', tex)
    tex = re.sub(r'\\tY', r'\\mathsf{Y}', tex)
    tex = re.sub(r'\\tS', r'\\mathsf{S}', tex)
    tex = re.sub(r'\\tU', r'\\mathsf{U}', tex)
    tex = re.sub(r'\\tN', r'\\mathsf{N}', tex)
    tex = re.sub(r'\\Ob', r'\\mathsf{O}', tex)
    tex = re.sub(r'\\Pe', r'\\mathsf{P}', tex)
    tex = re.sub(r'\\tA', r'\\mathsf{A}', tex)
    tex = re.sub(r'\\Always', r'\\mathsf{A}', tex)
    tex = re.sub(r'\\Sometimes', r'\\mathsf{S}', tex)
    tex = re.sub(r'\\Mostly', r'\\mathsf{M}', tex)
    tex = re.sub(r'\\stit', r'\\mathsf{stit}', tex)
    tex = re.sub(r'\\OK', r'\\mathsf{N}', tex)
    tex = re.sub(r'\\strictif', r'\,\\unicode{x297D}\,', tex)
    tex = re.sub(r'\\boxright', r'\\mathrel{\\mathop\\Box}\\mathrel{\\mkern-2.5mu}\\rightarrow', tex)
    return tex


def fix_gather(tex):
    """Replace gather environments with flalign to enforce left alignment."""
    pattern = re.compile(r'\\begin{gather(\*?)}(.*?)\\end{gather\*?}', re.DOTALL)

    def repl(match):
        environ = 'flalign*' if match.group(1) else 'flalign'
        body = match.group(2).strip()
        body = re.sub(r'^(.*?)(\\\\|$)', r'\\quad & \1 &\2', body, flags=re.MULTILINE)
        return f'\\begin{{{environ}}}\n{body}\n\\end{{{environ}}}'

    return pattern.sub(repl, tex)


def escape_labeled_items(tex):
    r"""
    Escape labeled \item to preserve the label.

    I sometimes use '\item[(*)] Principle' to label a Principle. make4ht turns
    this into a list item with a bullet point. We want to preserve the label.

    \item[(*)] Principle => \item[(*)] ITEMLABEL(*)ENDITEMLABEL Principle
    """
    tex = re.sub(r'\\item\[(.+?)\]', r'\\item[\1] ITEMLABEL\1ENDITEMLABEL', tex)
    return tex


def escape_intext_links(tex):
    r"""Insert content to restore links to definitions and observations etc.

    make4ht doesn't find links to tcolorbox definitions. So we do this:
    \begin{definition}{Basic Model}{basicmodel} =>  \begin{definition}{Basic Model ANCHORdef:basicmodelENDANCHOR}{basicmodel}
    \ref{def:basicmodel} => REFdef:basicmodelENDREF
    \begin{observation}{replacement-theorem} => \begin{observation}{replacement-theorem} ANCHORobs:replacement-theoremENDANCHOR
    \ref{obs:replacement-theorem} => REFobs:replacement-theoremENDREF

    We also replace references to page numbers:
    blahblah.\label{claim:replacement} blah => blahblah.ANCHORclaim:replacementENDANCHOR blah
    'on p.\ \pageref{table:systems}' => 'PAGEREFtable:systemsENDPAGEREF' => <a...>here</a>
    'on page \pageref{table:systems}' => 'PAGEREFtable:systemsENDPAGEREF' => <a...>here</a>
    'from page \pageref{table:systems}' => 'PAGEREFtable:systemsENDPAGEREF' => <a...>here</a>
    """
    tex = re.sub(r'\\begin{definition}\{(.*)\}\{([^}]+)\}', r'\\begin{definition}{\1 ANCHORdef:\2ENDANCHOR}{\2}', tex)
    tex = re.sub(r'\\ref\{def:([^}]+)\}', r'REFdef:\1ENDREF', tex)
    tex = re.sub(r'\\begin{observation}\{([^}]+)\}', r'\\begin{observation}{\1} ANCHORobs:\1ENDANCHOR', tex)
    tex = re.sub(r'\\ref\{obs:([^}]+)\}', r'REFobs:\1ENDREF', tex)
    # page number references:
    tex = re.sub(r'\\label\{([^}]+)\}', r'\\label{\1}ANCHOR\1ENDANCHOR', tex)
    tex = re.sub(r'(?:on|from|at)\s+(?:p\.|page)\\?\s+\\pageref\{([^}]+)\}', r'PAGEREF\1ENDPAGEREF', tex)
    return tex


def restore_intext_links():
    """Restore links to definitions and observations etc.

    <p> Definition 1.2: Basic Model ANCHORdef:basicmodelENDANCHOR</p>
    <p>See REFdef:basicmodelENDREF</p>
    <p> Observation 1.1:</p></div><div class="tcolorbox-content"><p>ANCHORobs:semantic-deduction-theoremENDANCHOR

    Also links to pages:
    <p>blahblah.ANCHORclaim:replacementENDANCHOR blah</p>
    <p>'we saw this PAGEREFclaim:replacementENDPAGEREF'</p>
    """
    from pprint import pprint
    anchors = {}  # 'def:basicmodel' => ('02-models.html', '2.2')
                  # 'claim:replacement' => ('02-models.html', '')
    # First build the anchors dictionary
    for htmlfile in html_files():
        html = read_file(html_path + '/' + htmlfile)

        def extract_anchor(match):
            anchors[match.group(2)] = (htmlfile, match.group(1))
            definition_text = match.group(0).split('ANCHOR')[0].strip().rstrip(':')
            return definition_text + '<a id="' + match.group(2) + '"></a>'

        pattern = r"""
        (?:Definition|Observation)
        \s*([\d\.]+)              # chapter and section number
        [^<]*?                    # optional text like ': Basic Model '
        (?:<\s*\/?[^>]+>\s*)*     # optional tags, but no text in between
        ANCHOR(.+?)ENDANCHOR
        """
        html = re.sub(pattern, extract_anchor, html, flags=re.DOTALL|re.VERBOSE)
        # simple pageref anchors:
        html = re.sub(r'()ANCHOR(.+?)ENDANCHOR', extract_anchor, html)
        write_file(html_path + '/' + htmlfile, html)

    pprint(anchors)

    # Now replace the link placeholders
    for htmlfile in html_files():
        html = read_file(html_path + '/' + htmlfile)

        def replace_ref(match, pageref=False):
            if match.group(1) not in anchors:
                print('Missing anchor:', match.group(1))
                return '??'
            filename, num = anchors[match.group(1)]
            if pageref:
                num = 'here'
            return f'<a class="locallink" href="{filename}#{match.group(1)}">{num}</a>'

        html = re.sub(r'REF(.+?)ENDREF', replace_ref, html)
        html = re.sub(r'PAGEREF(.+?)ENDPAGEREF', lambda m: replace_ref(m, True), html)
        write_file(html_path + '/' + htmlfile, html)


def make4ht(verbose=False):
    """Run make4ht to create HTML."""
    # with open(tmp_path+ "/href_db", mode="wt") as f:
    #     json.dump(hrefdb, f)

    tex4ht_options = [
        '2',   # split at chapter level
        # 'nominitoc',  # don't include tables of contents in each chapter
        # 'sec-filename',  # use filenames based on chapter titles
        # 'mathml',  # use MathML for math -- throws errors
        'mathjax',  # use MathJax as fallback
        # 'svg',  # use SVG images
        'enumerate+',  # enumerated list elements that keep the list couter value
        'fn-in',  # footnotes on each html page
    ]
    command = (
        f'cd {tmp_path} && '  # Change directory to the temporary path
        'make4ht '  # Call make4ht
        f'{"-a debug " if verbose else ""}'
        '-c mytex4ht.cfg '  # configuration file
        '--xetex '  # Use XeLaTeX engine for processing
        '--utf8 '  # Ensure UTF-8 encoding is used
        '-f html5 '  # Use HTML5 output format
        'logic2.tex '  # Main input file
        f'"{",".join(tex4ht_options)}" '  # tex4ht options
        f'-d ../{html_path} '  # Output directory
        '&& cd -'  # Return to the original directory
    )
    print(command)
    result = subprocess.run(command, shell=True, check=False, text=True)
    if result.stdout:
        print(result.stdout)
    if result.returncode != 0:
        print("Command failed with exit status", result.returncode)
        if result.stderr:
            print(result.sterr)
        # exit(1)


def save_or_restore_make4ht_output(restore=False):
    """
    Save output of make4ht to allow fake runs for debugging.

    We copy the html output of make4ht to a subdirectory of tmp_path. If fake is
    True, we instead copy the saved output back to html_path.
    """
    if not restore:
        shutil.copytree(html_path, tmp_path + '/html')
    else:
        # keep logic2.css!
        shutil.copyfile(html_path + '/logic2.css', tmp_path + '/html/logic2.css')
        shutil.rmtree(html_path)
        shutil.copytree(tmp_path + '/html', html_path)


def rename_html_files():
    """Rename HTML files to match chapter filenames."""
    mapping = {}
    mapping['logic2li1.html'] = 'toc.html'
    mapping['logic2li2.html'] = '00-preface.html'
    # Rename 'logic2ch1.html' to '01-operators.html', etc.":
    tex_chapters = tex_files()
    maxch = 0
    for f in os.listdir(html_path):
        m = re.search(r'logic2ch(\d+).*\.html', f)
        if m:
            chapter_num = m.group(1)
            maxch = max(maxch, int(chapter_num))
            if len(chapter_num) == 1:
                chapter_num = '0' + chapter_num
            try:
                chapter_file = next(ch for ch in tex_chapters if ch.startswith(chapter_num))
                new_name = chapter_file.replace('.tex', '.html')
                mapping[f] = new_name
            except StopIteration:
                print("No chapter file found for", f)
                mapping[f] = 'answers.html'
    # fix answers.html if some chapters are commented out:
    mapping['logic2ch' + str(maxch) + '.html'] = 'answers.html'
    for old, new in mapping.items():
        print("Renaming", old, "to", new)
        shutil.move(html_path + '/' + old, html_path + '/' + new)
    adjust_links(mapping)


def adjust_links(mapping):
    """Adjust links in HTML files."""
    for htmlfile in os.listdir(html_path):
        if not htmlfile.endswith('.html'):
            continue
        html = read_file(html_path + '/' + htmlfile)
        for old, new in mapping.items():
            html = html.replace(old, new)
        write_file(html_path + '/' + htmlfile, html)


def fix_toc_links():
    """Fix broken TOC links to chapter sections."""
    # We also make the local link names nices. So we first extract all section headings from all chapters:
    mapping = {}
    for htmlfile in html_files():
        html = read_file(html_path + '/' + htmlfile)
        # <h3 class="sectionHead"><span class="titlemark">1.1</span>  <a 
        # id="x4-40001.1"></a>A new language</h3>
        m = re.findall(r'<h3 class="sectionHead"><span.+?>(.+?)<.*?id="([^"]+)"></a>', html, re.DOTALL)
        for num, old_id in m:
            print("Replacing", old_id, "with", 'sec-' + num.replace('.', '-'))
            mapping[old_id] = 'sec-' + num.replace('.', '-')
        # fix toc links:
        # <span class='sectionToc'><span class='ec-lmr-10x-x-109'>1.4  </span><a href='logic2ch1.html#duality' id='QQ2-4-8'><span class='ec-lmr-10x-x-109'>Duality</span></a></span>
        m = re.findall(r"class='sectionToc'><span.+?>(.+?) +</span><a href='(.+?)#(.+?)'", html)
        for num, filename, old_hash in m:
            old_name = filename + '#' + old_hash
            new_name = filename + '#sec-' + num.replace('.', '-')
            print("Replacing", old_name, "with", new_name)
            mapping[old_name] = new_name
        # <span class='chapterToc'><span class='ec-lmr-10x-x-109'>1 </span><a href='01-operators.html#modal-operators' id='QQ2-4-4'><span class='ec-lmr-10x-x-109'>Modal Operators</span></a></span>
        m = re.findall(r"class='chapterToc'>.+<a href='(.+?)#(.+?)'", html)
        for filename, old_hash in m:
            old_name = filename + '#' + old_hash
            print("Replacing", old_name, "with", filename)
            mapping[old_name] = filename
    adjust_links(mapping)


def fix_html():
    """Fix HTML files after conversion."""
    restore_intext_links()
    for htmlfile in html_files():
        html = read_file(html_path + '/' + htmlfile)
        html = remove_comments(html)
        html = embed_in_template(html, htmlfile)
        html = fix_tcolorboxes(html, htmlfile)
        html = fix_item_labels(html)
        html = fix_layout(html)
        write_file(html_path + '/' + htmlfile, html)


def remove_comments(html):
    """Remove comments from HTML."""
    return re.sub(r'<!--.+?-->', '', html, flags=re.DOTALL)


def embed_in_template(html, filename):
    """Embed HTML files in template."""
    template = read_file('html_template.html')
    template = template.replace('{{year}}', str(datetime.datetime.now().year))
    toc = read_toc()
    template = template.replace('{{toc}}', '\n'.join(toc))
    body = re.split(r'<body\s*>', html, maxsplit=1)[1].rsplit('</body')[0]
    body = re.sub(r'<div class=.crosslinks.>.+?</div>', '', body, flags=re.DOTALL)
    # insert link to next chapter:
    chapter_toc = (t for t in toc if 'chapterToc' in t)
    try:
        next(t for t in chapter_toc if filename in t)
        next_link = next(chapter_toc)
        body += f'<div class="nextchapter">Next chapter: {next_link}</div>'
    except StopIteration:
        pass
    template = template.replace("{{content}}", body)
    title = 'Logic 2: Modal Logic'
    m = re.search(r'<h2 class=.chapterHead[^>?]+>(.+)</h2>', body, flags=re.DOTALL)
    if m:
        title += ' | ' + re.sub(r'<[^>]+>', '', m.group(1))
    template = template.replace("{{title}}", title)
    return template


def read_toc():
    """Return TOC as list of <a>s."""
    toc_html = read_file(html_path + '/toc.html')
    toc_links = re.findall(r'<span class=.(chapterToc|sectionToc).><span[^>]*>([\d.]*)\s*</span><a href=.([^"\']+).><span[^>]*>([^<]+)</span></a></span>', toc_html)
    toc = [f'<a class="{level}" href="{href}">{num} {name}</a>' for level, num, href, name in toc_links]
    if len(toc) == 0:
        print("TOC not found in toc.html")
    return toc


def fix_item_labels(html):
    r"""Fix item labels that were escaped in LaTeX.

    <li> ITEMLABEL(*)ENDITEMLABEL => <li class="nobullet"><span class="itemlabel">(*)</span>
    """
    html = re.sub(r'<li[^>]*>\s*(?:<p[^>]*>)?\s*ITEMLABEL(.+?)ENDITEMLABEL',
                  r'<li class="nobullet"><span class="itemlabel">\1</span>',
                  html, flags=re.DOTALL)
    # remove ITEMLABEL(*)ENDITEMLABEL accidentally inserted into other kinds of items:
    html = re.sub(r'ITEMLABEL.+?ENDITEMLABEL', '', html)
    return html


def fix_layout(html):
    """Fix layout issues in HTML."""
    html = fix_mathjax_linebreaks(html)
    # remove anchors in lists that add a linebreak:
    html = re.sub(r'(<li class=.enumerate.[^>]*>)\s*<a\s+id=.[^\'"]+[\'"]></a>', r'\1', html)
    # remove whitespace before section titles:
    html = re.sub(r'(<span class=.titlemark.>.+?</span>) *', r'\1', html)
    # widen too narrow tex, e.g. in $\Kn\!\neg\!\Kn\!\neg p$
    html = re.sub(r'\\!\s*\\', r'\\', html)
    # remove \hspace{-xxx} from math elements:
    html = re.sub(r'\\hspace\s*\{[^}]+\}', '', html)
    # remove empty table rows:
    html = re.sub(r'<tr>\s*<td[^>]*>\s*</td>\s*</tr>', '', html)
    return html


def fix_mathjax_linebreaks(html):
    r"""
    Fix linebreaks after mathjax elements.

    mathjax turns '... \( x \);' into '...</mjx-container>;' and nothing
    prevents a line break just before the semicolon. We don't want a line break
    there, so we wrap '\( x \);' in a no-wrap span.
    """
    html = re.sub(r'(\\\((?:[^\\)]|\\[^)])+\\\)[;.,?!\)])', r'<span class="nowrap">\1</span>', html)
    return html


def fix_tcolorboxes(html, htmlfile):
    """
    Fix missing or excessive </div> closings in tcolorboxes.

    There are two problems.

    First, "tcolorbox ducument" divs in the answers chapter aren't properly
    closed: there's neither a closing tag for the <div class="tcolorbox
    document"> nor for the embedded <div class="tcolorbox-content"> or
    even divs inside that!
    """
    pattern = r'''
        (<div\s+class=.tcolorbox\s+document.+?class=.tcolorbox-content.>.+?) # the box
        \s*(?=<div\s+class=.tcolorbox|<h3) # something after the box
        '''

    def repl(match):
        soup = BeautifulSoup(match.group(1), 'html.parser')
        fixed = str(soup)
        if fixed != match.group(1):
            print("fixing tcolorbox", match.group(1)[:60], "in", htmlfile)
            return fixed
        return match.group(0)

    html = re.sub(pattern, repl, html, flags=re.DOTALL|re.VERBOSE)
    """
    Second, "tcolorbox proof" divs have an extra closing </div> at the end.
    """
    pattern = r'(<div class=.tcolorbox proof.+?class=.tcolorbox-content.>.+?)</div>\s*</div>\s*</div>'

    def repl(match):
        print("removing third closing div for", match.group(1)[:40], "in", htmlfile)
        return match.group(1) + '</div></div>'

    html = re.sub(pattern, repl, html, flags=re.DOTALL)
    """
    Another minor issue, while we're here: the tcolorboxes for lemmas and
    theorems have class "tcolorbox tcolorbox", which makes them impossible to
    specifically style in the CSS. We change their class to "tcolorbox obs".
    """
    html = re.sub("class=.tcolorbox tcolorbox", "class='tcolorbox obs'", html)

    return html


def create_index():
    """Create index.html."""
    html = read_file(html_path + '/toc.html')
    html = re.sub(r'<h2.+?</h2>', '', html)
    shutil.copyfile('doclicense.png', html_path + '/doclicense.png')
    write_file(html_path + '/index.html', html)


def check_links():
    """Check for missing link targets ('??')."""
    for htmlfile in html_files():
        html = read_file(html_path + '/' + htmlfile)
        if '??' in html:
            print("Missing link targets in", htmlfile)


def read_file(filename):
    """Read file and return contents."""
    with open(filename) as f:
        return f.read()


def write_file(filename, data):
    """Write data to file."""
    with open(filename, mode="wt") as f:
        f.write(data)


if __name__ == "__main__":
    main()
