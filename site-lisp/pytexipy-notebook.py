'''
DESCRIPTION

pytexipy-notebook connects to an inprocess ipython kernel, executes
notebook code, and displays the results automatically in a LaTeX
buffer.

INSTALL

(pymacs-load "/usr/share/emacs23/site-lisp/pytexipy-notebook")
(global-set-key [f1] 'pytexipy-notebook-run-py-code) ; or choose any key you like

For minted-TeX integration, add this to your custom-set-variables
'(preview-LaTeX-command (quote ("%`%l -shell-escape \"\\nonstopmode\\nofiles\\PassOptionsToPackage{"
("," . preview-required-option-list) "}{preview}\\AtBeginDocument{\\ifx\\ifPreview\\undefined"
 preview-default-preamble "\\fi}\"%' %t")))

FEATURES

1) When you are in \begin{minted} and \end{minted} blocks,
call 'pytexipy-notebook-run-py-code, and all code in that block will
be sent to a ipython kernel and the result will be displayed
underneath. If on \inputminted{python}{file.py} block, code will be
loaded from script filename between the curly braces.

Results will be placed in \begin{verbatim}, \end{verbatim} blocks
right next to the code, with one space in between. If a verbatim blocks
already exists there, it will be refreshed. If not, it will be added.

2) If plt.show() is detected in code block, all previous code in
buffer will be scanned for plt.savefig(..) commands. Say there were 5
of them, in this case show() will be replaced with
plt.savefig('[file]_6.png').

LIMITATIONS:

* For now, there is one kernel per Emacs session. For another kernel
  with another scope, a new Emacs process needs to spawned.

'''

from __future__ import print_function
from StringIO import StringIO
from IPython.kernel.inprocess.blocking import BlockingInProcessKernelClient
from IPython.kernel.inprocess.manager import InProcessKernelManager
from IPython.kernel.inprocess.ipkernel import InProcessKernel
from IPython.core.interactiveshell import InteractiveShell
from IPython.utils.io import capture_output

from Pymacs import lisp
import re, sys, time, os
interactions = {}
kernels = {}

# make digits into length two - i.e. 1 into 01
def two_digit(i): return "0"+str(i) if i < 10 else str(i)

def decorated_run_code(fn):
    def new_run_code(*args, **kwargs):
        res = fn(*args, **kwargs)
        setattr(args[0], "last_known_outflag", res)
        return res
    return new_run_code

# wrapping run_code method inside InteractiveShell, we trap the return
# code here which is 1 for failure, 0 for good, there was no other
# way to sense an error for its callers. _get_exc_info is no good,
# because it will keep returning the same errors until the next error
# resets its state. 
InteractiveShell.run_code = decorated_run_code(InteractiveShell.run_code)    

def get_kernel_pointer(buffer):
    lisp.message("getting kernel for " + buffer)
    if buffer not in kernels:
        lisp.message("creating new " + buffer)
        km = InProcessKernelManager()
        km.start_kernel()
        kc = BlockingInProcessKernelClient(kernel=km.kernel)
        kc.start_channels()
        kernel = InProcessKernel()
        kernels[buffer] = (kc,kernel,kernel.shell.get_ipython())
        # run this so that plt, np pointers are ready
        kc.shell_channel.execute('%pylab inline')
        kc.shell_channel.execute('%load_ext autoreload')        
        kc.shell_channel.execute('%autoreload 2')

    return kernels[buffer]

def get_block_content(start_tag, end_tag):
    remember_where = lisp.point()
    block_end = lisp.search_forward(end_tag)
    block_begin = lisp.search_backward(start_tag)
    content = lisp.buffer_substring(block_begin, block_end)
    content = re.sub("\\\\begin{minted}.*?{python}","",content)
    content = re.sub("\\\\end{minted}","",content)
    lisp.goto_char(remember_where)
    return block_begin, block_end, content

def get_buffer_content_prev(bend):
    where_am_i = lisp.point()
    lisp.beginning_of_buffer(); st = lisp.point()
    s = lisp.buffer_substring(st,bend)
    lisp.goto_char(where_am_i)
    return s

def run_py_code():
    remember_where = lisp.point()
    # check if the line contains \inputminted
    lisp.beginning_of_line()
    l1 = lisp.point()
    lisp.end_of_line()
    l2 = lisp.point()
    line = lisp.buffer_substring(l1,l2)
    # if code comes from file
    if "\\inputminted" in line:
        lisp.message(line)
        py_file = re.search("\{python\}\{(.*?)\}", line).groups(1)[0]
        # get code content from file
        curr_dir = os.path.dirname(lisp.buffer_file_name())
        content = open(curr_dir + "/" + py_file).read()
        block_end = l2 # end of block happens to be end of include file line
        lisp.goto_char(remember_where)
    else:
        # get code content from latex
        block_begin,block_end,content = get_block_content("\\begin{minted}","\\end{minted}")

    #lisp.message(content)
        
    # we have code content at this point

    # scan content to find plt.plot(). if there is, scan buffer
    # previous to *here* to determine order of _this_ plt.plot(), and
    # give it an appropiate index that will be appended to the end of
    # the .png image file, i.e. [buffer name]_[index].png. plt.plot()
    # commands will be replaced by the corresponding plt.savefig
    # command.

    # generate savefig for execution code (no output in emacs yet)
    bc = get_buffer_content_prev(block_begin)
    plt_count_before = len(re.findall('plt\.savefig\(',bc))
    base = os.path.splitext(lisp.buffer_name())[0]
    f = '%s_%s.png' % (base, two_digit(plt_count_before+1))
    rpl = "plt.savefig('%s')" % f
    show_replaced = True if "plt.show()" in content else False
    content=content.replace("plt.show()",rpl)
    include_graphics_command = "\\includegraphics[height=6cm]{%s}" % f

    (kc,kernel,ip) = get_kernel_pointer(lisp.buffer_name())
    start = time.time()
    res = ''
    with capture_output() as io:
        ip.run_cell(content)
    res = io.stdout
    if kernel.shell.last_known_outflag:
        etype, value, tb = kernel.shell._get_exc_info()
        res = str(etype) + " " + str(value)  + "\n"        
    elapsed = (time.time() - start)
    # replace this unnecessary message so output becomes blank
    if res and len(res) > 0:  # if result not empty
        res = res.replace("Populating the interactive namespace from numpy and matplotlib\n","")
        display_results(block_end, res) # display it
    else:
        display_results(block_end, "") 
        lisp.goto_char(block_end)

    # generate includegraphics command
    if show_replaced:
        lisp.forward_line(2) # skip over end verbatim, leave one line emtpy
        lisp.insert(include_graphics_command + '\n')
        lisp.backward_line_nomark(1) # skip over end verbatim, leave one line emtpy        
        lisp.goto_char(remember_where)
        lisp.replace_string("plt.show()",rpl,None,block_begin,block_end)
        
    lisp.goto_char(remember_where)
    if "plt.savefig" in content: lisp.preview_buffer()
    
    lisp.message("Ran in " + str(elapsed) + " seconds")

def verb_exists():
    remem = lisp.point()
    lisp.forward_line(2)
    lisp.beginning_of_line()
    verb_line_b = lisp.point()
    lisp.end_of_line()
    verb_line_e = lisp.point()
    verb_line = lisp.buffer_substring(verb_line_b, verb_line_e)
    lisp.goto_char(remem)
    if "\\begin{verbatim}" in verb_line: return True
    else: return False
    
def display_results(end_block, res):
    remem = lisp.point()
    res=res.replace("\r","")
    lisp.goto_char(end_block)
    verb_begin = None
    # if there is output block, remove it whether there output or not
    # because it will be replaced anyway if something exists
    if verb_exists():
        verb_begin,verb_end,content = get_block_content("\\begin{verbatim}","\\end{verbatim}")
        lisp.delete_region(verb_begin, verb_end)
        lisp.goto_char(remem)

    # now if there _is_ output, then go to beginning of old verbatim
    # output (if removed), if not, this is brand new output, move
    # down 2 lines, insert the output 
    if res and len(res) > 0:
        if verb_begin:
            lisp.goto_char(verb_begin)
        else:
            lisp.forward_line(2)
        lisp.insert("\\begin{verbatim}\n")
        lisp.insert(res)
        lisp.insert("\\end{verbatim}")

def thing_at_point():
    right_set = left_set = set(['\n',' '])
    curridx = lisp.point()
    curr=''
    while (curr in right_set) == False:
        curr = lisp.buffer_substring(curridx, curridx+1)
        curridx += 1
    start = curridx-1
        
    curridx = lisp.point()
    curr=''
    while (curr in left_set) == False:
        curr = lisp.buffer_substring(curridx-1, curridx)
        curridx -= 1
    end = curridx+1
        
    s = lisp.buffer_substring(start, end)
    return s, end
        
def complete_py():
    thing, start = thing_at_point()
    lisp.message(thing)
    (kc,kernel,ip) = get_kernel_pointer(lisp.buffer_name())
    text, matches = ip.complete(thing)
    lisp.switch_to_buffer("*pytexipy*")
    lisp.kill_buffer(lisp.get_buffer("*pytexipy*"))
    lisp.switch_to_buffer_other_window("*pytexipy*")
    lisp.insert(thing)
    for item in matches:        
        lisp.insert(item)
        lisp.insert("\n")
            
interactions[run_py_code] = ''
interactions[complete_py] = ''
