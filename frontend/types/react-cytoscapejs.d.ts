declare module 'react-cytoscapejs' {
  import type { ComponentType } from 'react';
  import type { CytoscapeOptions, ElementDefinition, Stylesheet } from 'cytoscape';

  export interface CytoscapeComponentProps {
    elements: ElementDefinition[];
    style?: React.CSSProperties;
    layout?: CytoscapeOptions['layout'];
    stylesheet?: Stylesheet[];
    minZoom?: number;
    maxZoom?: number;
    [key: string]: unknown;
  }

  const CytoscapeComponent: ComponentType<CytoscapeComponentProps>;
  export default CytoscapeComponent;
}
