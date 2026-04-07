// --- Search ---
const searchInput = document.getElementById("tree-search");
const searchResults = document.getElementById("search-results");
let searchTimeout = null;

if (searchInput && searchResults) {
  searchInput.addEventListener("input", () => {
    clearTimeout(searchTimeout);
    const q = searchInput.value.trim();
    if (q.length < 2) {
      searchResults.classList.remove("active");
      return;
    }
    searchTimeout = setTimeout(() => doSearch(q), 300);
  });

  searchInput.addEventListener("blur", () => {
    setTimeout(() => searchResults.classList.remove("active"), 200);
  });
}

async function doSearch(q) {
  try {
    const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
    const data = await res.json();
    if (data.results.length === 0) {
      searchResults.innerHTML =
        '<div class="search-result-item">Cap resultat</div>';
    } else {
      searchResults.innerHTML = data.results
        .map(
          (r) => `
        <div class="search-result-item" onclick="loadTree('${r.id}')">
          ${r.name}
          <span class="years">${r.birth_year || "?"} - ${r.death_year || (r.is_alive ? "viu/a" : "?")}</span>
        </div>`
        )
        .join("");
    }
    searchResults.classList.add("active");
  } catch (e) {
    // ignore
  }
}

// --- Tree rendering ---
const svg = d3.select("#tree-svg");
const container = document.getElementById("tree-container");
let g; // main group for zoom
let zoomBehavior;
let currentData = null;

const NODE_W = 160;
const NODE_H = 50;
const MARGIN = { top: 40, right: 40, bottom: 40, left: 40 };

function initSvg() {
  svg.selectAll("*").remove();
  g = svg.append("g");

  zoomBehavior = d3
    .zoom()
    .scaleExtent([0.2, 3])
    .on("zoom", (event) => {
      g.attr("transform", event.transform);
    });

  svg.call(zoomBehavior);
}

async function loadTree(personId) {
  if (searchResults) searchResults.classList.remove("active");
  if (searchInput) searchInput.value = "";
  document.getElementById("tree-info").textContent = "Carregant...";

  // Clean personId for URL (remove @ symbols)
  const cleanId = personId.replace(/@/g, "");

  try {
    const res = await fetch(
      `/api/tree/${cleanId}?generations_up=3&generations_down=2`
    );
    if (!res.ok) throw new Error("Not found");
    currentData = await res.json();
    renderTree(currentData);
    document.getElementById("tree-info").textContent = currentData.name;
  } catch (e) {
    document.getElementById("tree-info").textContent =
      "Error carregant l'arbre";
  }
}

function renderTree(data) {
  initSvg();

  const width = container.clientWidth;
  const height = container.clientHeight;

  // Build ancestor hierarchy (going UP)
  const ancestorRoot = buildAncestorHierarchy(data);
  // Build descendant hierarchy (going DOWN)
  const descendantRoot = buildDescendantHierarchy(data);

  const ancestorNodes = [];
  const ancestorLinks = [];
  const descendantNodes = [];
  const descendantLinks = [];

  // Layout ancestors (upward from root)
  if (ancestorRoot.children && ancestorRoot.children.length > 0) {
    const treeLayout = d3.tree().nodeSize([NODE_W + 20, NODE_H + 40]);
    const hierarchy = d3.hierarchy(ancestorRoot);
    treeLayout(hierarchy);
    hierarchy.each((d) => {
      // Flip Y to go upward
      d.y = -d.y;
      ancestorNodes.push(d);
    });
    hierarchy.links().forEach((l) => ancestorLinks.push(l));
  } else {
    // Just the root node for ancestors
    ancestorNodes.push({ x: 0, y: 0, data: ancestorRoot });
  }

  // Layout descendants (downward from root)
  if (descendantRoot.children && descendantRoot.children.length > 0) {
    const treeLayout = d3.tree().nodeSize([NODE_W + 20, NODE_H + 40]);
    const hierarchy = d3.hierarchy(descendantRoot);
    treeLayout(hierarchy);
    hierarchy.each((d) => {
      // Offset downward (skip root, it's already in ancestors)
      d.y = d.y + NODE_H + 40;
      if (d.depth > 0) descendantNodes.push(d);
    });
    hierarchy.links().forEach((l) => {
      if (l.source.depth === 0) {
        // Connect from root (y=0) to first children
        l.source = { x: 0, y: 0, data: descendantRoot };
      }
      descendantLinks.push(l);
    });
  }

  // Draw ancestor links
  g.selectAll(".ancestor-link")
    .data(ancestorLinks)
    .join("path")
    .attr("class", "link")
    .attr("d", (d) => {
      return `M${d.source.x},${d.source.y - NODE_H / 2}
              C${d.source.x},${(d.source.y + d.target.y) / 2}
               ${d.target.x},${(d.source.y + d.target.y) / 2}
               ${d.target.x},${d.target.y + NODE_H / 2}`;
    });

  // Draw descendant links
  g.selectAll(".descendant-link")
    .data(descendantLinks)
    .join("path")
    .attr("class", "link")
    .attr("d", (d) => {
      const sy = d.source.data === descendantRoot ? 0 : d.source.y;
      const sx = d.source.data === descendantRoot ? 0 : d.source.x;
      return `M${sx},${sy + NODE_H / 2}
              C${sx},${(sy + d.target.y) / 2}
               ${d.target.x},${(sy + d.target.y) / 2}
               ${d.target.x},${d.target.y - NODE_H / 2}`;
    });

  // Draw all nodes
  const allNodes = [...ancestorNodes, ...descendantNodes];
  const nodeGroup = g
    .selectAll(".node")
    .data(allNodes)
    .join("g")
    .attr("class", (d) => {
      let cls = "node";
      if (d.data.id === data.id) cls += " root";
      return cls;
    })
    .attr("transform", (d) => `translate(${d.x - NODE_W / 2},${d.y - NODE_H / 2})`)
    .style("cursor", "pointer")
    .on("click", (event, d) => {
      if (d.data.id && d.data.id !== data.id) {
        loadTree(d.data.id);
      }
    });

  // Node background
  nodeGroup
    .append("rect")
    .attr("width", NODE_W)
    .attr("height", NODE_H)
    .attr("rx", 6);

  // Photo
  nodeGroup.each(function (d) {
    if (d.data.photo) {
      d3.select(this)
        .append("image")
        .attr("href", `/photos/${d.data.photo}`)
        .attr("x", 4)
        .attr("y", 5)
        .attr("width", 28)
        .attr("height", 28)
        .attr("clip-path", "circle(14px at 14px 14px)");
    }
  });

  // Name
  nodeGroup
    .append("text")
    .attr("x", (d) => (d.data.photo ? 38 : 8))
    .attr("y", 20)
    .text((d) => {
      const name = d.data.name || "?";
      return name.length > 18 ? name.substring(0, 17) + "..." : name;
    });

  // Years
  nodeGroup
    .append("text")
    .attr("class", "years-text")
    .attr("x", (d) => (d.data.photo ? 38 : 8))
    .attr("y", 35)
    .text((d) => {
      const b = d.data.birth_year || "?";
      const death = d.data.death_year || (d.data.is_alive ? "viu/a" : "?");
      return `${b} - ${death}`;
    });

  // Draw spouse next to root
  if (data.spouses && data.spouses.length > 0) {
    const spouse = data.spouses[0];
    const spouseX = NODE_W / 2 + 20;
    const spouseY = -NODE_H / 2;

    // Spouse link
    g.append("line")
      .attr("class", "link spouse-link")
      .attr("x1", NODE_W / 2)
      .attr("y1", 0)
      .attr("x2", spouseX)
      .attr("y2", 0);

    const sg = g
      .append("g")
      .attr("class", "node")
      .attr("transform", `translate(${spouseX},${spouseY})`)
      .style("cursor", "pointer")
      .on("click", () => loadTree(spouse.id));

    sg.append("rect").attr("width", NODE_W).attr("height", NODE_H).attr("rx", 6);

    if (spouse.photo) {
      sg.append("image")
        .attr("href", `/photos/${spouse.photo}`)
        .attr("x", 4)
        .attr("y", 5)
        .attr("width", 28)
        .attr("height", 28);
    }

    sg.append("text")
      .attr("x", spouse.photo ? 38 : 8)
      .attr("y", 20)
      .text(
        spouse.name.length > 18
          ? spouse.name.substring(0, 17) + "..."
          : spouse.name
      );

    sg.append("text")
      .attr("class", "years-text")
      .attr("x", spouse.photo ? 38 : 8)
      .attr("y", 35)
      .text(`${spouse.birth_year || "?"} - ${spouse.death_year || "?"}`);
  }

  // Center the view
  const transform = d3.zoomIdentity.translate(width / 2, height / 2).scale(0.8);
  svg.transition().duration(500).call(zoomBehavior.transform, transform);
}

function buildAncestorHierarchy(data) {
  const node = {
    id: data.id,
    name: data.name,
    birth_year: data.birth_year,
    death_year: data.death_year,
    photo: data.photo,
    is_alive: data.is_alive,
    children: [],
  };

  if (data.father) {
    node.children.push(buildAncestorHierarchy(data.father));
  }
  if (data.mother) {
    node.children.push(buildAncestorHierarchy(data.mother));
  }

  return node;
}

function buildDescendantHierarchy(data) {
  const node = {
    id: data.id,
    name: data.name,
    birth_year: data.birth_year,
    death_year: data.death_year,
    photo: data.photo,
    is_alive: data.is_alive,
  };

  if (data.children && data.children.length > 0) {
    node.children = data.children.map((c) => buildDescendantHierarchy(c));
  }

  return node;
}

// --- Zoom controls ---
function zoomIn() {
  svg.transition().duration(300).call(zoomBehavior.scaleBy, 1.3);
}

function zoomOut() {
  svg.transition().duration(300).call(zoomBehavior.scaleBy, 0.7);
}

function resetZoom() {
  const width = container.clientWidth;
  const height = container.clientHeight;
  const transform = d3.zoomIdentity.translate(width / 2, height / 2).scale(0.8);
  svg.transition().duration(500).call(zoomBehavior.transform, transform);
}

// Initialize
initSvg();
