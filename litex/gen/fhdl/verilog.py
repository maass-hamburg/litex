#
# This file is part of Migen and has been adapted/modified for LiteX.
#
# This file is Copyright (c) 2013-2014 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2013-2018 Florent Kermarrec <florent@enjoy-digital.fr>
# This file is Copyright (c) 2013-2017 Robert Jordens <jordens@gmail.com>
# This file is Copyright (c) 2016-2018 whitequark <whitequark@whitequark.org>
# This file is Copyright (c) 2017 Adam Greig <adam@adamgreig.com>
# This file is Copyright (c) 2016 Ben Reynwar <ben@reynwar.net>
# This file is Copyright (c) 2018 David Craven <david@craven.ch>
# This file is Copyright (c) 2015 Guy Hutchison <ghutchis@gmail.com>
# This file is Copyright (c) 2013 Nina Engelhardt <nina.engelhardt@omnium-gatherum.de>
# This file is Copyright (c) 2018 Robin Ole Heinemann <robin.ole.heinemann@t-online.de>
# SPDX-License-Identifier: BSD-2-Clause

from functools import partial
from operator import itemgetter
import collections

from migen.fhdl.structure import *
from migen.fhdl.structure import _Operator, _Slice, _Assign, _Fragment
from migen.fhdl.tools import *
from migen.fhdl.namer import build_namespace
from migen.fhdl.conv_output import ConvOutput
from migen.fhdl.specials import Memory

from litex.gen.fhdl.memory import memory_emit_verilog
from litex.build.tools import generated_banner

# Reserved Keywords  -------------------------------------------------------------------------------

_ieee_1800_2017_verilog_reserved_keywords = {
     "accept_on",          "alias",          "always",         "always_comb",          "always_ff",
  "always_latch",            "and",          "assert",              "assign",             "assume",
     "automatic",         "before",           "begin",                "bind",               "bins",
        "binsof",            "bit",           "break",                 "buf",             "bufif0",
        "bufif1",           "byte",            "case",               "casex",              "casez",
          "cell",        "chandle",         "checker",               "class",           "clocking",
          "cmos",         "config",           "const",          "constraint",            "context",
      "continue",          "cover",      "covergroup",          "coverpoint",              "cross",
      "deassign",        "default",        "defparam",              "design",            "disable",
          "dist",             "do",            "edge",                "else",                "end",
       "endcase",     "endchecker",        "endclass",         "endclocking",          "endconfig",
   "endfunction",    "endgenerate",        "endgroup",        "endinterface",          "endmodule",
    "endpackage",   "endprimitive",      "endprogram",         "endproperty",        "endsequence",
    "endspecify",       "endtable",         "endtask",                "enum",              "event",
    "eventually",         "expect",          "export",             "extends",             "extern",
         "final",    "first_match",             "for",               "force",            "foreach",
       "forever",           "fork",        "forkjoin",            "function",           "generate",
        "genvar",         "global",          "highz0",              "highz1",                 "if",
           "iff",         "ifnone",     "ignore_bins",        "illegal_bins",         "implements",
       "implies",         "import",          "incdir",             "include",            "initial",
         "inout",          "input",          "inside",            "instance",                "int",
       "integer",   "interconnect",       "interface",           "intersect",               "join",
      "join_any",      "join_none",           "large",                 "let",            "liblist",
       "library",          "local",      "localparam",               "logic",            "longint",
   "macromodule",        "matches",          "medium",             "modport",             "module",
          "nand",        "negedge",         "nettype",                 "new",           "nexttime",
          "nmos",            "nor", "noshowcancelled",                 "not",             "notif0",
        "notif1",           "null",              "or",              "output",            "package",
        "packed",      "parameter",            "pmos",             "posedge",          "primitive",
      "priority",        "program",        "property",           "protected",              "pull0",
         "pull1",       "pulldown",          "pullup", "pulsestyle_ondetect", "pulsestyle_onevent",
          "pure",           "rand",           "randc",            "randcase",       "randsequence",
         "rcmos",           "real",        "realtime",                 "ref",                "reg",
     "reject_on",        "release",    "      repeat",            "restrict",             "return",
         "rnmos",          "rpmos",           "rtran",            "rtranif0",           "rtranif1",
      "s_always",   "s_eventually",      "s_nexttime",             "s_until",       "s_until_with",
      "scalared",       "sequence",        "shortint",           "shortreal",      "showcancelled",
        "signed",          "small",            "soft",               "solve",            "specify",
     "specparam",         "static",          "string",              "strong",            "strong0",
       "strong1",         "struct",           "super",             "supply0",            "supply1",
"sync_accept_on", "sync_reject_on",           "table",              "tagged",               "task",
          "this",     "throughout",            "time",       "timeprecision",           "timeunit",
          "tran",        "tranif0",         "tranif1",                 "tri",               "tri0",
          "tri1",         "triand",           "trior",              "trireg",               "type",
       "typedef",   "       union",          "unique",             "unique0",           "unsigned",
         "until",     "until_with",         "untyped",                 "use",           "   uwire",
           "var",       "vectored",         "virtual",                "void",               "wait",
    "wait_order",           "wand",            "weak",               "weak0",              "weak1",
         "while",       "wildcard",            "wire",                "with",             "within",
           "wor",           "xnor",             "xor",
}

# Print Signal -------------------------------------------------------------------------------------

def _print_signal(ns, s):
    return "{signed}{vector}{name}".format(
        signed = "" if (not s.signed) else "signed ",
        vector = "" if ( len(s) <= 1) else f"[{str(len(s)-1) }:0] ",
        name   = ns.get_name(s)
    )

# Print Constant -----------------------------------------------------------------------------------

def _print_constant(node):
    return "{sign}{bits}'d{value}".format(
        sign  = "" if node.value >= 0 else "-",
        bits  = str(node.nbits),
        value = abs(node.value),
    ), node.signed

# Print Operator -----------------------------------------------------------------------------------

(UNARY, BINARY, TERNARY) = (1, 2, 3)

def _print_operator(ns, node):
    operator = node.op
    operands = node.operands
    arity    = len(operands)
    assert arity in [UNARY, BINARY, TERNARY]

    def to_signed(r):
        return f"$signed({{1'd0 {r}}}))"

    # Unary Operator.
    if arity == UNARY:
        r1, s1 = _print_expression(ns, operands[0])
        # Negation Operator.
        if operator == "-":
            # Negate and convert to signed if not already.
            r = "-" + (r1 if s1 else to_signed(r1))
            s = True
        # Other Operators.
        else:
            r = operator + r1
            s = s1

    # Binary Operator.
    if arity == BINARY:
        r1, s1 = _print_expression(ns, operands[0])
        r2, s2 = _print_expression(ns, operands[1])
        # Convert all expressions to signed when at least one is signed.
        if operator not in ["<<<", ">>>"]:
            if s2 and not s1:
                r1 = to_signed(r1)
            if s1 and not s2:
                r2 = to_signed(r2)
        r = f"{r1} {operator} {r2}"
        s = s1 or s2

    # Ternary Operator.
    if arity == TERNARY:
        assert operator == "m"
        r1, s1 = _print_expression(ns, operands[0])
        r2, s2 = _print_expression(ns, operands[1])
        r3, s3 = _print_expression(ns, operands[2])
        # Convert all expressions to signed when at least one is signed.
        if s2 and not s3:
            r3 = to_signed(r3)
        if s3 and not s2:
            r2 = to_signed(r2)
        r = f"{r1} ? {r2} : {r3}"
        s = s2 or s3

    return f"({r})", s

# Print Slice --------------------------------------------------------------------------------------

def _print_slice(ns, node):
    assert (node.stop - node.start) >= 1
    if (isinstance(node.value, Signal) and len(node.value) == 1):
        assert node.start == 0
        sr = "" # Avoid slicing 1-bit Signals.
    else:
        sr = f"[{node.stop-1}:{node.start}]" if (node.stop - node.start) > 1 else f"[{node.start}]"
    r, s = _print_expression(ns, node.value)
    return r + sr, s

# Print Cat ----------------------------------------------------------------------------------------

def _print_cat(ns, node):
    l = [_print_expression(ns, v)[0] for v in reversed(node.l)]
    return "{" + ", ".join(l) + "}", False

# Print Replicate ----------------------------------------------------------------------------------

def _print_replicate(ns, node):
    return "{" + str(node.n) + "{" + _print_expression(ns, node.v)[0] + "}}", False

# Print Expression ---------------------------------------------------------------------------------

def _print_expression(ns, node):
    # Constant.
    if isinstance(node, Constant):
        return _print_constant(node)

    # Signal.
    elif isinstance(node, Signal):
        return ns.get_name(node), node.signed

    # Operator.
    elif isinstance(node, _Operator):
        return _print_operator(ns, node)

    # Slice.
    elif isinstance(node, _Slice):
        return _print_slice(ns, node)

    # Cat.
    elif isinstance(node, Cat):
        return _print_cat(ns, node)

    # Replicate.
    elif isinstance(node, Replicate):
        return _print_replicate(ns, node)

    # Unknown.
    else:
        raise TypeError(f"Expression of unrecognized type: '{type(node).__name__}'")


# Print Node ---------------------------------------------------------------------------------------

(_AT_BLOCKING, _AT_NONBLOCKING, _AT_SIGNAL) = range(3)

def _print_node(ns, at, level, node, target_filter=None):
    if target_filter is not None and target_filter not in list_targets(node):
        return ""
    elif isinstance(node, _Assign):
        if at == _AT_BLOCKING:
            assignment = " = "
        elif at == _AT_NONBLOCKING:
            assignment = " <= "
        elif is_variable(node.l):
            assignment = " = "
        else:
            assignment = " <= "
        return "\t"*level + _print_expression(ns, node.l)[0] + assignment + _print_expression(ns, node.r)[0] + ";\n"
    elif isinstance(node, collections.abc.Iterable):
        return "".join(_print_node(ns, at, level, n, target_filter) for n in node)
    elif isinstance(node, If):
        r = "\t"*level + "if (" + _print_expression(ns, node.cond)[0] + ") begin\n"
        r += _print_node(ns, at, level + 1, node.t, target_filter)
        if node.f:
            r += "\t"*level + "end else begin\n"
            r += _print_node(ns, at, level + 1, node.f, target_filter)
        r += "\t"*level + "end\n"
        return r
    elif isinstance(node, Case):
        if node.cases:
            r = "\t"*level + "case (" + _print_expression(ns, node.test)[0] + ")\n"
            css = [(k, v) for k, v in node.cases.items() if isinstance(k, Constant)]
            css = sorted(css, key=lambda x: x[0].value)
            for choice, statements in css:
                r += "\t"*(level + 1) + _print_expression(ns, choice)[0] + ": begin\n"
                r += _print_node(ns, at, level + 2, statements, target_filter)
                r += "\t"*(level + 1) + "end\n"
            if "default" in node.cases:
                r += "\t"*(level + 1) + "default: begin\n"
                r += _print_node(ns, at, level + 2, node.cases["default"], target_filter)
                r += "\t"*(level + 1) + "end\n"
            r += "\t"*level + "endcase\n"
            return r
        else:
            return ""
    elif isinstance(node, Display):
        s = "\"" + node.s + "\""
        for arg in node.args:
            s += ", "
            if isinstance(arg, Signal):
                s += ns.get_name(arg)
            else:
                s += str(arg)
        return "\t"*level + "$display(" + s + ");\n"
    elif isinstance(node, Finish):
        return "\t"*level + "$finish;\n"
    else:
        raise TypeError("Node of unrecognized type: "+str(type(node)))

# Print Attribute ----------------------------------------------------------------------------------

def _print_attribute(attr, attr_translate):
    r = ""
    firsta = True
    for attr in sorted(attr,
                       key=lambda x: ("", x) if isinstance(x, str) else x):
        if isinstance(attr, tuple):
            # platform-dependent attribute
            attr_name, attr_value = attr
        else:
            # translated attribute
            at = attr_translate.get(attr, None)
            if at is None:
                continue
            attr_name, attr_value = at
        if not firsta:
            r += ", "
        firsta = False
        const_expr = "\"" + attr_value + "\"" if not isinstance(attr_value, int) else str(attr_value)
        r += attr_name + " = " + const_expr
    if r:
        r = "(* " + r + " *)"
    return r

# Print Module -------------------------------------------------------------------------------------

def _list_comb_wires(f):
    r = set()
    groups = group_by_targets(f.comb)
    for g in groups:
        if len(g[1]) == 1 and isinstance(g[1][0], _Assign):
            r |= g[0]
    return r

def _print_module(f, ios, name, ns, attr_translate,
                 reg_initialization):
    sigs         = list_signals(f) | list_special_ios(f, ins=True, outs=True, inouts=True)
    special_outs = list_special_ios(f, ins=False, outs=True,  inouts=True)
    inouts       = list_special_ios(f, ins=False, outs=False, inouts=True)
    targets      = list_targets(f) | special_outs
    wires        = _list_comb_wires(f) | special_outs
    r = "module " + name + "(\n"
    firstp = True
    for sig in sorted(ios, key=lambda x: x.duid):
        if not firstp:
            r += ",\n"
        firstp = False
        attr = _print_attribute(sig.attr, attr_translate)
        if attr:
            r += "\t" + attr
        sig.type = "wire"
        sig.name = ns.get_name(sig)
        if sig in inouts:
            sig.direction = "inout"
            r += "\tinout wire " + _print_signal(ns, sig)
        elif sig in targets:
            sig.direction = "output"
            if sig in wires:
                r += "\toutput wire " + _print_signal(ns, sig)
            else:
                sig.type = "reg"
                r += "\toutput reg " + _print_signal(ns, sig)
        else:
            sig.direction = "input"
            r += "\tinput wire " + _print_signal(ns, sig)
    r += "\n);\n\n"
    for sig in sorted(sigs - ios, key=lambda x: x.duid):
        attr = _print_attribute(sig.attr, attr_translate)
        if attr:
            r += attr + " "
        if sig in wires:
            r += "wire " + _print_signal(ns, sig) + ";\n"
        else:
            if reg_initialization:
                r += "reg " + _print_signal(ns, sig) + " = " + _print_expression(ns, sig.reset)[0] + ";\n"
            else:
                r += "reg " + _print_signal(ns, sig) + ";\n"
    r += "\n"
    return r

# Print Combinatorial Logic (Simulation) -----------------------------------------------------------

def _print_combinatorial_logic_sim(f, ns,
            display_run,
            dummy_signal,
            blocking_assign):
    r = ""
    if f.comb:
        if dummy_signal:
            # Generate a dummy event to get the simulator
            # to run the combinatorial process once at the beginning.
            syn_off = "// synthesis translate_off\n"
            syn_on = "// synthesis translate_on\n"
            dummy_s = Signal(name_override="dummy_s")
            r += syn_off
            r += "reg " + _print_signal(ns, dummy_s) + ";\n"
            r += "initial " + ns.get_name(dummy_s) + " <= 1'd0;\n"
            r += syn_on


        from collections import defaultdict

        target_stmt_map = defaultdict(list)

        for statement in flat_iteration(f.comb):
            targets = list_targets(statement)
            for t in targets:
                target_stmt_map[t].append(statement)

        groups = group_by_targets(f.comb)

        for n, (t, stmts) in enumerate(target_stmt_map.items()):
            assert isinstance(t, Signal)
            if len(stmts) == 1 and isinstance(stmts[0], _Assign):
                r += "assign " + _print_node(ns, _AT_BLOCKING, 0, stmts[0])
            else:
                if dummy_signal:
                    dummy_d = Signal(name_override="dummy_d")
                    r += "\n" + syn_off
                    r += "reg " + _print_signal(ns, dummy_d) + ";\n"
                    r += syn_on

                r += "always @(*) begin\n"
                if display_run:
                    r += "\t$display(\"Running comb block #" + str(n) + "\");\n"
                if blocking_assign:
                    r += "\t" + ns.get_name(t) + " = " + _print_expression(ns, t.reset)[0] + ";\n"
                    r += _print_node(ns, _AT_BLOCKING, 1, stmts, t)
                else:
                    r += "\t" + ns.get_name(t) + " <= " + _print_expression(ns, t.reset)[0] + ";\n"
                    r += _print_node(ns, _AT_NONBLOCKING, 1, stmts, t)
                if dummy_signal:
                    r += syn_off
                    r += "\t" + ns.get_name(dummy_d) + " = " + ns.get_name(dummy_s) + ";\n"
                    r += syn_on
                r += "end\n"
    r += "\n"
    return r

# Print Combinatorial Logic (Synthesis) ------------------------------------------------------------

def _print_combinatorial_logic_synth(f, ns, blocking_assign):
    r = ""
    if f.comb:
        groups = group_by_targets(f.comb)

        for n, g in enumerate(groups):
            if len(g[1]) == 1 and isinstance(g[1][0], _Assign):
                r += "assign " + _print_node(ns, _AT_BLOCKING, 0, g[1][0])
            else:
                r += "always @(*) begin\n"
                if blocking_assign:
                    for t in g[0]:
                        r += "\t" + ns.get_name(t) + " = " + _print_expression(ns, t.reset)[0] + ";\n"
                    r += _print_node(ns, _AT_BLOCKING, 1, g[1])
                else:
                    for t in g[0]:
                        r += "\t" + ns.get_name(t) + " <= " + _print_expression(ns, t.reset)[0] + ";\n"
                    r += _print_node(ns, _AT_NONBLOCKING, 1, g[1])
                r += "end\n"
    r += "\n"
    return r

# Print Synchronous Logic --------------------------------------------------------------------------

def _print_synchronous_logic(f, ns):
    r = ""
    for k, v in sorted(f.sync.items(), key=itemgetter(0)):
        r += "always @(posedge " + ns.get_name(f.clock_domains[k].clk) + ") begin\n"
        r += _print_node(ns, _AT_SIGNAL, 1, v)
        r += "end\n\n"
    return r

# Print Specials -----------------------------------------------------------------------------------

def _print_specials(overrides, specials, ns, add_data_file, attr_translate):
    r = ""
    for special in sorted(specials, key=lambda x: x.duid):
        if hasattr(special, "attr"):
            attr = _print_attribute(special.attr, attr_translate)
            if attr:
                r += attr + " "
        # Replace Migen Memory's emit_verilog with our implementation.
        if isinstance(special, Memory):
            pr = memory_emit_verilog(special, ns, add_data_file)
        else:
            pr = call_special_classmethod(overrides, special, "emit_verilog", ns, add_data_file)
        if pr is None:
            raise NotImplementedError("Special " + str(special) + " failed to implement emit_verilog")
        r += pr
    return r

# Convert FHDL to Verilog --------------------------------------------------------------------------

class DummyAttrTranslate(dict):
    def __getitem__(self, k):
        return (k, "true")

def convert(f, ios=set(), name="top",
    special_overrides    = dict(),
    attr_translate       = DummyAttrTranslate(),
    create_clock_domains = True,
    display_run          = False,
    reg_initialization   = True,
    dummy_signal         = True,
    blocking_assign      = False,
    regular_comb         = True):

    # Create ConvOutput.
    r = ConvOutput()

    # Convert to FHDL's fragments is not already done.
    if not isinstance(f, _Fragment):
        f = f.get_fragment()

    # Verify/Create Clock Domains.
    for cd_name in sorted(list_clock_domains(f)):
        # Try to get Clock Domain.
        try:
            f.clock_domains[cd_name]
        # If not found, create it if enabled:
        except:
            if create_clock_domains:
                cd = ClockDomain(cd_name)
                f.clock_domains.append(cd)
                ios |= {cd.clk, cd.rst}
            # Or raise Error.
            else:
                msg = f"""Unresolved clock domain {cd_name}, availables:\n"""
                for f in f.clock_domains:
                    msg += f"- {f.name}\n"
                raise Exception(msg)

    # Lower complex slices.
    f = lower_complex_slices(f)

    # Insert resets.
    insert_resets(f)

    # Lower basics.
    f = lower_basics(f)

    # Lower specials.
    f, lowered_specials = lower_specials(special_overrides, f)

    # Lower basics (for basics included in specials).
    f = lower_basics(f)

    # IOs backtrace/naming.
    for io in sorted(ios, key=lambda x: x.duid):
        if io.name_override is None:
            io_name = io.backtrace[-1][0]
            if io_name:
                io.name_override = io_name

    # Build NameSpace.
    # ----------------
    ns = build_namespace(
        signals = (
            list_signals(f) |
            list_special_ios(f, ins=True, outs=True, inouts=True) |
            ios),
        reserved_keywords = _ieee_1800_2017_verilog_reserved_keywords
    )
    ns.clock_domains = f.clock_domains

    # Build Verilog.
    # --------------
    verilog = generated_banner("//")

    # Module Top.
    verilog += _print_module(f, ios, name, ns, attr_translate, reg_initialization=reg_initialization)

    # Combinatorial Logic.
    if regular_comb:
        verilog += _print_combinatorial_logic_synth(f, ns,
            blocking_assign = blocking_assign
        )
    else:
        verilog += _print_combinatorial_logic_sim(f, ns,
            display_run     = display_run,
            dummy_signal    = dummy_signal,
            blocking_assign = blocking_assign
        )

    # Synchronous Logic.
    verilog += _print_synchronous_logic(f, ns)

    # Specials
    verilog += _print_specials(special_overrides, f.specials - lowered_specials,
        ns, r.add_data_file, attr_translate)

    # Module End.
    verilog += "endmodule\n"


    r.set_main_source(verilog)
    r.ns = ns

    return r
