#![no_main]
use libfuzzer_sys::fuzz_target;
use std::collections::HashMap;

// ---- Duplicated pure-Rust logic from src/router.rs (no PyO3) ----

#[derive(Debug, Clone)]
struct Endpoint {
    id: String,
    param_names: Vec<String>,
}

#[derive(Debug, Clone)]
struct Node {
    prefix: String,
    children: Vec<Node>,
    param_child: Option<Box<Node>>,
    wildcard_child: Option<Box<Node>>,
    endpoints: HashMap<String, Endpoint>,
}

impl Node {
    fn new(prefix: &str) -> Self {
        Node {
            prefix: prefix.to_string(),
            children: Vec::new(),
            param_child: None,
            wildcard_child: None,
            endpoints: HashMap::new(),
        }
    }
}

#[derive(Debug, Clone)]
enum Segment {
    Static(String),
    Param(String),
    Wildcard(String),
}

fn parse_pattern(pattern: &str) -> Vec<Segment> {
    let trimmed = pattern.trim_matches('/');
    if trimmed.is_empty() {
        return vec![];
    }
    trimmed
        .split('/')
        .map(|seg| {
            if seg.starts_with('{') && seg.ends_with('}') {
                let inner = &seg[1..seg.len() - 1];
                if let Some(name) = inner.strip_suffix(":*") {
                    Segment::Wildcard(name.to_string())
                } else {
                    Segment::Param(inner.to_string())
                }
            } else {
                Segment::Static(seg.to_string())
            }
        })
        .collect()
}

fn insert_route(node: &mut Node, segments: &[Segment], depth: usize, method: &str, endpoint: Endpoint) {
    if depth >= segments.len() {
        node.endpoints.insert(method.to_string(), endpoint);
        return;
    }
    match &segments[depth] {
        Segment::Static(s) => {
            let idx = node.children.iter().position(|c| c.prefix == *s);
            if let Some(idx) = idx {
                insert_route(&mut node.children[idx], segments, depth + 1, method, endpoint);
            } else {
                let mut child = Node::new(s);
                insert_route(&mut child, segments, depth + 1, method, endpoint);
                node.children.push(child);
            }
        }
        Segment::Param(_) => {
            if node.param_child.is_none() {
                node.param_child = Some(Box::new(Node::new("")));
            }
            insert_route(node.param_child.as_mut().unwrap(), segments, depth + 1, method, endpoint);
        }
        Segment::Wildcard(_) => {
            if node.wildcard_child.is_none() {
                node.wildcard_child = Some(Box::new(Node::new("")));
            }
            node.wildcard_child.as_mut().unwrap().endpoints.insert(method.to_string(), endpoint);
        }
    }
}

fn match_segments<'a>(
    node: &'a Node,
    segments: &[&str],
    depth: usize,
    method: &str,
    param_values: &mut Vec<String>,
) -> Option<&'a Endpoint> {
    if depth >= segments.len() {
        return node.endpoints.get(method);
    }
    let segment = segments[depth];
    for child in &node.children {
        if child.prefix == segment {
            if let Some(result) = match_segments(child, segments, depth + 1, method, param_values) {
                return Some(result);
            }
        }
    }
    if let Some(ref param_child) = node.param_child {
        param_values.push(segment.to_string());
        if let Some(result) = match_segments(param_child, segments, depth + 1, method, param_values) {
            return Some(result);
        }
        param_values.pop();
    }
    if let Some(ref wildcard_child) = node.wildcard_child {
        let remaining = segments[depth..].join("/");
        param_values.push(remaining);
        if let Some(result) = wildcard_child.endpoints.get(method) {
            return Some(result);
        }
        param_values.pop();
    }
    None
}

// ---- Fuzz target ----

fuzz_target!(|data: &[u8]| {
    let Ok(input) = std::str::from_utf8(data) else { return };

    // Limit input size to prevent OOM
    if input.len() > 2048 {
        return;
    }

    // Fuzz pattern parsing
    let segments = parse_pattern(input);

    // Build a router with the fuzzed pattern as a route
    let mut root = Node::new("");
    let param_names: Vec<String> = segments
        .iter()
        .filter_map(|s| match s {
            Segment::Param(n) | Segment::Wildcard(n) => Some(n.clone()),
            _ => None,
        })
        .collect();
    let endpoint = Endpoint {
        id: "fuzz".to_string(),
        param_names,
    };
    insert_route(&mut root, &segments, 0, "GET", endpoint);

    // Try matching the same input as a path
    let normalized = if input.len() > 1 && input.ends_with('/') {
        &input[..input.len() - 1]
    } else {
        input
    };
    let trimmed = normalized.trim_start_matches('/');
    let path_segments: Vec<&str> = if trimmed.is_empty() {
        vec![]
    } else {
        trimmed.split('/').collect()
    };

    // Limit segment count to prevent stack overflow in recursive matching
    if path_segments.len() <= 64 {
        let mut values = Vec::new();
        let _ = match_segments(&root, &path_segments, 0, "GET", &mut values);
    }
});
