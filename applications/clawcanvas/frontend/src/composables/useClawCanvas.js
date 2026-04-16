export function createDemoDocument() {
  return {
    id: 'demo_clawcanvas',
    name: 'ClawCanvas Demo Skill',
    description: 'A MASFactory-based skill design workflow.',
    inputs: {
      query: 'Design a skill studio based on MASFactory.'
    },
    attributes: {},
    manifest: {
      name: 'clawcanvas_demo_skill',
      version: '0.1.0',
      description: 'Demo skill package exported from ClawCanvas.',
      tags: ['demo', 'workflow', 'skill'],
      tools: [
        {
          name: 'web_search',
          binding: 'future',
          description: 'Reserved tool binding metadata'
        }
      ],
      knowledge: [
        {
          title: 'Skill Definition',
          text: 'Skill = tools + domain knowledge + behavior rules.'
        }
      ],
      behavior: {
        style: 'structured',
        rules: ['Explain the workflow clearly.', 'Keep the output actionable.']
      }
    },
    nodes: [
      {
        id: 'start',
        type: 'start',
        label: 'Start',
        position: { x: 80, y: 240 },
        config: {}
      },
      {
        id: 'researcher',
        type: 'agent',
        label: 'Researcher',
        position: { x: 340, y: 160 },
        config: {
          instructions: 'Analyze the user request and extract the workflow goals.',
          prompt_template: 'User request: {query}',
          pull_keys: { query: 'Original user request' },
          push_keys: { analysis: 'Structured analysis' },
          behavior_rules: ['Focus on requirements.', 'List assumptions briefly.'],
          knowledge: []
        }
      },
      {
        id: 'formatter',
        type: 'custom',
        label: 'Formatter',
        position: { x: 660, y: 70 },
        config: {
          mode: 'template',
          templates: {
            analysis_card: 'Summary: {analysis}'
          },
          pull_keys: { analysis: 'Structured analysis' },
          push_keys: { analysis_card: 'Formatted card' },
          static_outputs: {},
          pick_keys: {}
        }
      },
      {
        id: 'designer',
        type: 'agent',
        label: 'Designer',
        position: { x: 960, y: 260 },
        config: {
          instructions: 'Turn the analysis into a skill design brief.',
          prompt_template: 'Request: {query}\nAnalysis: {analysis}\nCard: {analysis_card}',
          pull_keys: {
            query: 'Original request',
            analysis: 'Analysis result',
            analysis_card: 'Formatted analysis card'
          },
          push_keys: { answer: 'Final design brief' },
          behavior_rules: ['Prefer architecture-level guidance.'],
          knowledge: [
            {
              title: 'Product Goal',
              text: 'ClawCanvas packages MASFactory workflows into publishable skills.'
            }
          ]
        }
      },
      {
        id: 'end',
        type: 'end',
        label: 'End',
        position: { x: 1260, y: 220 },
        config: {}
      }
    ],
    edges: [
      {
        id: 'edge_1',
        source: 'start',
        target: 'researcher',
        mapping: { query: 'User request' }
      },
      {
        id: 'edge_2',
        source: 'researcher',
        target: 'formatter',
        mapping: { analysis: 'Analysis result' }
      },
      {
        id: 'edge_3',
        source: 'researcher',
        target: 'designer',
        mapping: { query: 'Original request', analysis: 'Analysis result' }
      },
      {
        id: 'edge_4',
        source: 'formatter',
        target: 'designer',
        mapping: { analysis_card: 'Formatted analysis card' }
      },
      {
        id: 'edge_5',
        source: 'designer',
        target: 'end',
        mapping: { answer: 'Final answer' }
      }
    ]
  };
}

export function nextNodeId(document, prefix) {
  const taken = new Set(document.nodes.map((node) => node.id));
  let index = 1;
  while (taken.has(`${prefix}_${index}`)) {
    index += 1;
  }
  return `${prefix}_${index}`;
}

export function buildNodeTemplate(type, id) {
  if (type === 'agent') {
    return {
      id,
      type: 'agent',
      label: `Agent ${id.split('_')[1]}`,
      position: { x: 240, y: 160 },
      config: {
        instructions: 'Describe this node behavior.',
        prompt_template: '{message}',
        pull_keys: { message: 'Input message' },
        push_keys: { message: 'Output message' },
        behavior_rules: [],
        knowledge: [],
        tools: []
      }
    };
  }

  if (type === 'custom') {
    return {
      id,
      type: 'custom',
      label: `Custom ${id.split('_')[1]}`,
      position: { x: 240, y: 220 },
      config: {
        mode: 'template',
        templates: { message: 'Transformed: {message}' },
        static_outputs: {},
        pick_keys: {},
        pull_keys: { message: 'Input message' },
        push_keys: { message: 'Output message' }
      }
    };
  }

  if (type === 'loop') {
    return {
      id,
      type: 'loop',
      label: `Loop ${id.split('_')[1]}`,
      position: { x: 240, y: 280 },
      config: {
        max_iterations: 3,
        terminate_when: {
          mode: 'key_truthy',
          key: 'done',
          value: true
        },
        body: {
          type: 'agent',
          instructions: 'Review the current state and decide whether the task is complete.',
          prompt_template: 'Current state: {message}',
          input_mapping: { message: 'Loop input' },
          output_mapping: { message: 'Loop output', done: 'Stop flag' },
          pull_keys: { message: 'Loop input' },
          push_keys: { message: 'Loop output', done: 'Stop flag' },
          behavior_rules: [],
          knowledge: [],
          tools: []
        }
      }
    };
  }

  throw new Error(`Unsupported node template type: ${type}`);
}
