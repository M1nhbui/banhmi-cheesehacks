export function add3dBuildingsLayer(map: any) {
    if (map.getLayer("3d-buildings")) return
  
    const styleLayers = map.getStyle()?.layers
    const labelLayerId = styleLayers?.find((l: any) => l.type === "symbol" && l.layout?.["text-field"])?.id
  
    map.addLayer(
      {
        id: "3d-buildings",
        source: "composite",
        "source-layer": "building",
        filter: ["==", "extrude", "true"],
        type: "fill-extrusion",
        minzoom: 13,
        paint: {
          "fill-extrusion-color": "#9aa0a6",
          "fill-extrusion-height": ["*", ["coalesce", ["get", "height"], 6], 0.22],
          "fill-extrusion-base": ["*", ["coalesce", ["get", "min_height"], 0], 0.22],
          "fill-extrusion-opacity": 0.5,
        },
      },
      labelLayerId
    )
  }