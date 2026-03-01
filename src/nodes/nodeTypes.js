import LLMNode from './LLMNode';
import ToolNode from './ToolNode';
import InputNode from './InputNode';
import OutputNode from './OutputNode';
import ConditionalNode from './ConditionalNode';

export const nodeTypes = {
  llmNode: LLMNode,
  toolNode: ToolNode,
  inputNode: InputNode,
  outputNode: OutputNode,
  conditionalNode: ConditionalNode,
};
