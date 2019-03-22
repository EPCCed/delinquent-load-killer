from fparser.common.readfortran import *
from fparser.common.sourceinfo import FortranFormat
from fparser.one.parsefortran import FortranParser
from fparser.one.block_statements import BeginSource, Program, Subroutine, Do, Module, Function, If, \
  IfThen, Assignment, Where, EndDo, Import
import sys
import os

current_loops=[]
all_loops=[]
procedure_names=[]
import_line=0

class LoopDescriptor:
  def __init__(self, start_line_number, loop_variable):
    self.start_line_number=start_line_number
    self.loop_variable=loop_variable
    self.do_instrument=False
    self.contained_loops=[]
    self.derived_loop_variables=[]
    self.end_line_number=None
    self.messages={}
    self.instrumented_lines=[]

  def appendMessage(self, line, message):
    if (line not in self.messages):
      self.messages[line] = []

    self.messages[line].append(message)

  def instrument(self, line_num):
    self.do_instrument=True
    self.instrumented_lines.append(line_num)

  def setInstrument(self, do_instrument):
    self.do_instrument=do_instrument

  def getInstrument(self):
    return self.do_instrument

  def getLoopVariable(self):
    return self.loop_variable

  def setEndLineNumber(self, end_line_number):
    self.end_line_number=end_line_number

  def getStartLineNumber(self):
    return self.start_line_number

  def getEndLineNumber(self):
    return self.end_line_number

  def appendDerivedVariable(self, var):
    self.derived_loop_variables.append(var)

  def isVariableDependency(self, var):
    if (self.getLoopVariable() == var): return True
    if (var in self.derived_loop_variables): return True
    return False

  def appendContainedLoop(self, loop):
    self.contained_loops.append(loop)

  def getMessages(self):
    return self.messages

  def getInstrumentedLines(self):
    return self.instrumented_lines

  def clearInstrumentOfContainedLoops(self):
    for loop in self.contained_loops:
      loop.setInstrument(False)
      self.messages.update(loop.getMessages())
      self.instrumented_lines.append(loop.getInstrumentedLines())
      loop.clearInstrumentOfContainedLoops()

def parseForFunctionSubroutineNames(ast):
  ast_type = type(ast)
  if (ast_type == BeginSource or ast_type == Program or ast_type == Subroutine or
          ast_type == Module or ast_type == Function or ast_type == If or ast_type == IfThen or
        ast_type == Where):
    if (ast_type == Subroutine or ast_type == Function):
      procedure_names.append(ast.name)
    for c in ast.content:
      parseForFunctionSubroutineNames(c)

def parse(ast):
  global import_line
  ast_type=type(ast)
  if (ast_type == BeginSource or ast_type == Program or ast_type == Subroutine or
          ast_type == Module or ast_type == Function or ast_type == If or ast_type == IfThen or
        ast_type == Where):
    if (ast_type == Module or ast_type == Program):
      import_line = ast.item.span[1]
    for c in ast.content:
      parse(c)
  if (ast_type == Do):
    loop_var=ast.loopcontrol.split("=")[0]
    ld=LoopDescriptor(ast.item.span[0], loop_var)
    if (len(current_loops) > 0):
      current_loops[-1].appendContainedLoop(ld)
    current_loops.append(ld)
    all_loops.append(ld)
    for c in ast.content:
      parse(c)
  if (ast_type == EndDo):
    current_loops[-1].setEndLineNumber(ast.item.span[1])
    current_loops.pop()
  if (ast_type == Assignment):
    var_name=name=ast.variable
    trackDerivedVariablesFromLoopVariable(str(ast.expr), var_name)
    if (len(current_loops) > 0):
      handleDependencyForVariable(var_name, ast.item.span[0])
      handleDependencyForRHS(ast, ast.item.span[0], str(ast.expr))

def handleDependencyForRHS(ast, line_num, rhs):
  for token in tokeniseExpression(rhs):
      handleDependencyForVariable(token, line_num)

def handleDependencyForVariable(var_token, line_num, array_in_nest=False):
  if ("(" in var_token):
    # Array access that we care about as inside a loop
    split_on_brace=var_token.split("(", 1)
    if (not array_in_nest):
      array_in_nest=split_on_brace[0] not in procedure_names

    accessor=split_on_brace[1].rsplit(')', 1)
    array_indexes=accessor[0]
    idx_location=0
    for access_index in array_indexes.split(","):
      access_index=access_index.strip()
      if ("(" in access_index):
        handleDependencyForVariable(access_index, line_num, array_in_nest)
      else:
        if (array_in_nest):
          cl, loop_nesting = findApplicableLoop(access_index)
          if (cl is not None):
            cl.instrument(line_num)
            if (split_on_brace[0] in procedure_names):
              # Accessing via a function call
              cl.appendMessage(line_num, "Possible indirect array access via function")
            else:
              # Accessing via variable directly
              if (loop_nesting == 0 and idx_location > 0):
                cl.appendMessage(line_num, "Fastest changing loop index, "+access_index+", is in location other than contiguous dimension")
      idx_location+=1

def trackDerivedVariablesFromLoopVariable(rhs, var_name):
  for token in tokeniseExpression(rhs):
    cl, loop_nesting = findApplicableLoop(token)
    if (cl is not None):
      cl.appendDerivedVariable(var_name)

def tokeniseExpression(expression):
  processed_expression = expression.replace('+', '@').replace('-', '@').replace('*', '@').replace('/', '@').replace('%', '@')
  tokens = []
  for token in processed_expression.split("@"):
    if (not token.isdigit()):
      tokens.append(token.strip())
  return tokens

def findApplicableLoop(access_index):
  last_count=0
  for cl in reversed(current_loops):
    if (cl.isVariableDependency(access_index)):
      return cl, last_count
    last_count+=1

  return None, None

def processIdentifiedLoopsForInstrumentation(all_loops, displayMessages):
  start_line_nums={}
  end_line_nums = {}
  for loop in all_loops:
    if (loop.getInstrument()):
      loop.clearInstrumentOfContainedLoops()

  instrument_count = 1
  for loop in all_loops:
    if (loop.getInstrument()):
      start_line_nums[loop.getStartLineNumber()]=loop
      end_line_nums[loop.getEndLineNumber()] = loop
      if (displayMessages):
        print("[" + str(instrument_count) + "] Instrumenting loop between lines " + str(
          loop.getStartLineNumber()) + " and " + str(loop.getEndLineNumber()))
        for line in loop.getInstrumentedLines():
          print("     ---- Instrumenting for line " + str(line))
          if (line in loop.getMessages()):
            for message in loop.getMessages()[line]:
              print("          Note: " + message)
        instrument_count += 1
  return start_line_nums, end_line_nums

def createInstrumentedFile(file_name, start_line_nums, end_line_nums):
  file_path=file_name.rsplit("/", 1)
  directory_path="."
  source_name=file_name
  if (len(file_path) == 2):
    directory_path=file_path[0]
    source_name=file_path[1]
  if not os.path.exists(directory_path+"/instrumented"):
    os.makedirs(directory_path+"/instrumented")
  f=open(file_name)
  f2 = open(directory_path+"/instrumented/"+source_name, "w")
  line_num=1
  for line in f:
    if (line_num in start_line_nums):
      f2.write("call DLKHunter_startEventEpoch()\n")
    f2.write(line)
    if (line_num in end_line_nums):
      f2.write("call DLKHunter_stopEventEpoch(__FILE__, __LINE__)\n")
    if (line_num == import_line):
      f2.write("use dlkhunter_mod\n")
    line_num+=1
  f.close()
  f2.close()

file_name=sys.argv[1]
file_ending=file_name.split(".")[1].strip()
free_form = file_ending != "f"
reader=FortranFileReader(file_name)
reader.set_format(FortranFormat(free_form, False))
parser = FortranParser(reader)
parser.parse()
parser.analyze()
parseForFunctionSubroutineNames(parser.block)
parse(parser.block)
start_line_nums, end_line_nums=processIdentifiedLoopsForInstrumentation(all_loops, True)
createInstrumentedFile(file_name, start_line_nums, end_line_nums)

