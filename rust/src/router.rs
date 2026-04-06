use pyo3::prelude::*;
use pyo3::types::PyDict;
use std::collections::HashMap;

/// Stored endpoint with its parameter names for reconstruction.
#[derive(Debug, Clone)]
struct Endpoint {
    id: String,
    /// Ordered list of param names encountered on the path to this endpoint.
    param_names: Vec<String>,
}

/// A node in the radix tree.
#[derive(Debug, Clone)]
struct Node {
    /// Static path segment for this node (empty for root).
    prefix: String,
    /// Static children.
    children: Vec<Node>,
    /// Param child node (matches any single segment).
    param_child: Option<Box<Node>>,
    /// Wildcard/catch-all child node (matches remaining path).
    wildcard_child: Option<Box<Node>>,
    /// Endpoints keyed by HTTP method. Each endpoint stores its own param names.
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

/// High-performance radix tree URL router.
///
/// Matches URL paths against registered patterns in O(path_length) time.
/// Supports static segments, named parameters (`{id}`), and wildcards (`{path:*}`).
#[pyclass]
#[derive(Debug, Clone)]
pub struct RadixRouter {
    root: Node,
    route_count: usize,
}

#[pymethods]
impl RadixRouter {
    #[new]
    fn new() -> Self {
        RadixRouter {
            root: Node::new(""),
            route_count: 0,
        }
    }

    /// Register a route pattern.
    ///
    /// Args:
    ///     method: HTTP method (GET, POST, etc.)
    ///     pattern: URL pattern (e.g., "/users/{id}/posts")
    ///     endpoint_id: Unique identifier for the endpoint
    fn add_route(&mut self, method: &str, pattern: &str, endpoint_id: &str) -> PyResult<()> {
        let segments = parse_pattern(pattern);
        let method_upper = method.to_uppercase();

        // Collect param names in order
        let param_names: Vec<String> = segments
            .iter()
            .filter_map(|s| match s {
                Segment::Param(name) => Some(name.clone()),
                Segment::Wildcard(name) => Some(name.clone()),
                _ => None,
            })
            .collect();

        let endpoint = Endpoint {
            id: endpoint_id.to_string(),
            param_names,
        };

        insert_route(&mut self.root, &segments, 0, &method_upper, endpoint);
        self.route_count += 1;
        Ok(())
    }

    /// Match a request path against registered routes.
    ///
    /// Returns:
    ///     Tuple of (endpoint_id, params_dict) or None if no match.
    fn match_route<'py>(
        &self,
        py: Python<'py>,
        method: &str,
        path: &str,
    ) -> PyResult<Option<(String, Bound<'py, PyDict>)>> {
        let method_upper = method.to_uppercase();

        // Normalize: strip trailing slash for matching (unless root)
        let normalized = if path.len() > 1 && path.ends_with('/') {
            &path[..path.len() - 1]
        } else {
            path
        };

        let trimmed = normalized.trim_start_matches('/');
        let segments: Vec<&str> = if trimmed.is_empty() {
            vec![]
        } else {
            trimmed.split('/').collect()
        };

        let mut param_values: Vec<String> = Vec::new();

        if let Some(endpoint) = match_segments(&self.root, &segments, 0, &method_upper, &mut param_values) {
            let dict = PyDict::new(py);
            for (name, value) in endpoint.param_names.iter().zip(param_values.iter()) {
                dict.set_item(name, value)?;
            }
            Ok(Some((endpoint.id.clone(), dict)))
        } else {
            Ok(None)
        }
    }

    /// Number of registered routes.
    #[getter]
    fn route_count(&self) -> usize {
        self.route_count
    }
}

/// Segment types parsed from a URL pattern.
#[derive(Debug, Clone)]
enum Segment {
    Static(String),
    Param(String),
    Wildcard(String),
}

/// Parse a URL pattern into segments.
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

/// Insert a route into the radix tree.
fn insert_route(
    node: &mut Node,
    segments: &[Segment],
    depth: usize,
    method: &str,
    endpoint: Endpoint,
) {
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
            let child = node.param_child.as_mut().unwrap();
            insert_route(child, segments, depth + 1, method, endpoint);
        }
        Segment::Wildcard(_) => {
            if node.wildcard_child.is_none() {
                node.wildcard_child = Some(Box::new(Node::new("")));
            }
            let child = node.wildcard_child.as_mut().unwrap();
            child.endpoints.insert(method.to_string(), endpoint);
        }
    }
}

/// Match path segments against the radix tree, collecting param values.
/// Returns the matched endpoint (which contains the correct param names).
fn match_segments<'a>(
    node: &'a Node,
    segments: &[&str],
    depth: usize,
    method: &str,
    param_values: &mut Vec<String>,
) -> Option<&'a Endpoint> {
    // Base case: consumed all segments
    if depth >= segments.len() {
        return node.endpoints.get(method);
    }

    let segment = segments[depth];

    // Try static children first (highest priority)
    for child in &node.children {
        if child.prefix == segment {
            if let Some(result) = match_segments(child, segments, depth + 1, method, param_values) {
                return Some(result);
            }
        }
    }

    // Try param child
    if let Some(ref param_child) = node.param_child {
        param_values.push(segment.to_string());

        if let Some(result) = match_segments(param_child, segments, depth + 1, method, param_values)
        {
            return Some(result);
        }

        param_values.pop(); // Backtrack
    }

    // Try wildcard child (catches remaining path)
    if let Some(ref wildcard_child) = node.wildcard_child {
        let remaining = segments[depth..].join("/");
        param_values.push(remaining);

        if let Some(result) = wildcard_child.endpoints.get(method) {
            return Some(result);
        }

        param_values.pop(); // Backtrack
    }

    None
}

/// Register the router submodule.
pub fn register(parent: &Bound<'_, PyModule>) -> PyResult<()> {
    parent.add_class::<RadixRouter>()?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_pattern_static() {
        let segments = parse_pattern("/users/list");
        assert_eq!(segments.len(), 2);
        assert!(matches!(&segments[0], Segment::Static(s) if s == "users"));
        assert!(matches!(&segments[1], Segment::Static(s) if s == "list"));
    }

    #[test]
    fn test_parse_pattern_param() {
        let segments = parse_pattern("/users/{id}");
        assert_eq!(segments.len(), 2);
        assert!(matches!(&segments[0], Segment::Static(s) if s == "users"));
        assert!(matches!(&segments[1], Segment::Param(s) if s == "id"));
    }

    #[test]
    fn test_parse_pattern_wildcard() {
        let segments = parse_pattern("/files/{path:*}");
        assert_eq!(segments.len(), 2);
        assert!(matches!(&segments[0], Segment::Static(s) if s == "files"));
        assert!(matches!(&segments[1], Segment::Wildcard(s) if s == "path"));
    }

    #[test]
    fn test_parse_root() {
        let segments = parse_pattern("/");
        assert_eq!(segments.len(), 0);
    }

    #[test]
    fn test_insert_and_match_static() {
        let mut root = Node::new("");
        let segments = parse_pattern("/users/list");
        let endpoint = Endpoint {
            id: "users_list".to_string(),
            param_names: vec![],
        };
        insert_route(&mut root, &segments, 0, "GET", endpoint);

        let mut values = Vec::new();
        let result = match_segments(&root, &["users", "list"], 0, "GET", &mut values);
        assert!(result.is_some());
        assert_eq!(result.unwrap().id, "users_list");
        assert!(values.is_empty());
    }

    #[test]
    fn test_insert_and_match_param() {
        let mut root = Node::new("");
        let segments = parse_pattern("/users/{id}");
        let endpoint = Endpoint {
            id: "user_detail".to_string(),
            param_names: vec!["id".to_string()],
        };
        insert_route(&mut root, &segments, 0, "GET", endpoint);

        let mut values = Vec::new();
        let result = match_segments(&root, &["users", "42"], 0, "GET", &mut values);
        assert!(result.is_some());
        assert_eq!(result.unwrap().id, "user_detail");
        assert_eq!(result.unwrap().param_names, vec!["id"]);
        assert_eq!(values, vec!["42"]);
    }

    #[test]
    fn test_static_priority_over_param() {
        let mut root = Node::new("");

        let ep1 = Endpoint {
            id: "user_me".to_string(),
            param_names: vec![],
        };
        insert_route(&mut root, &parse_pattern("/users/me"), 0, "GET", ep1);

        let ep2 = Endpoint {
            id: "user_detail".to_string(),
            param_names: vec!["id".to_string()],
        };
        insert_route(&mut root, &parse_pattern("/users/{id}"), 0, "GET", ep2);

        // Static "me" should match first
        let mut values = Vec::new();
        let result = match_segments(&root, &["users", "me"], 0, "GET", &mut values);
        assert_eq!(result.unwrap().id, "user_me");
        assert!(values.is_empty());

        // Other values should match param
        values.clear();
        let result = match_segments(&root, &["users", "42"], 0, "GET", &mut values);
        assert_eq!(result.unwrap().id, "user_detail");
        assert_eq!(values, vec!["42"]);
    }

    #[test]
    fn test_different_param_names_same_position() {
        let mut root = Node::new("");

        // Two routes sharing the same param position but with different param names
        let ep1 = Endpoint {
            id: "user_detail".to_string(),
            param_names: vec!["id".to_string()],
        };
        insert_route(&mut root, &parse_pattern("/users/{id}"), 0, "GET", ep1);

        let ep2 = Endpoint {
            id: "user_posts".to_string(),
            param_names: vec!["user_id".to_string()],
        };
        insert_route(
            &mut root,
            &parse_pattern("/users/{user_id}/posts"),
            0,
            "GET",
            ep2,
        );

        // GET /users/5 should use param name "id"
        let mut values = Vec::new();
        let result = match_segments(&root, &["users", "5"], 0, "GET", &mut values);
        assert_eq!(result.unwrap().id, "user_detail");
        assert_eq!(result.unwrap().param_names, vec!["id"]);
        assert_eq!(values, vec!["5"]);

        // GET /users/5/posts should use param name "user_id"
        values.clear();
        let result = match_segments(&root, &["users", "5", "posts"], 0, "GET", &mut values);
        assert_eq!(result.unwrap().id, "user_posts");
        assert_eq!(result.unwrap().param_names, vec!["user_id"]);
        assert_eq!(values, vec!["5"]);
    }

    #[test]
    fn test_nested_params() {
        let mut root = Node::new("");
        let endpoint = Endpoint {
            id: "user_post".to_string(),
            param_names: vec!["user_id".to_string(), "post_id".to_string()],
        };
        insert_route(
            &mut root,
            &parse_pattern("/users/{user_id}/posts/{post_id}"),
            0,
            "GET",
            endpoint,
        );

        let mut values = Vec::new();
        let result = match_segments(&root, &["users", "5", "posts", "42"], 0, "GET", &mut values);
        assert!(result.is_some());
        let ep = result.unwrap();
        assert_eq!(ep.id, "user_post");
        assert_eq!(ep.param_names, vec!["user_id", "post_id"]);
        assert_eq!(values, vec!["5", "42"]);
    }

    #[test]
    fn test_wildcard() {
        let mut root = Node::new("");
        let endpoint = Endpoint {
            id: "files_catch_all".to_string(),
            param_names: vec!["path".to_string()],
        };
        insert_route(
            &mut root,
            &parse_pattern("/files/{path:*}"),
            0,
            "GET",
            endpoint,
        );

        let mut values = Vec::new();
        let result = match_segments(
            &root,
            &["files", "a", "b", "c.txt"],
            0,
            "GET",
            &mut values,
        );
        assert!(result.is_some());
        assert_eq!(result.unwrap().id, "files_catch_all");
        assert_eq!(values, vec!["a/b/c.txt"]);
    }

    #[test]
    fn test_method_isolation() {
        let mut root = Node::new("");

        let ep1 = Endpoint {
            id: "list_users".to_string(),
            param_names: vec![],
        };
        insert_route(&mut root, &parse_pattern("/users"), 0, "GET", ep1);

        let ep2 = Endpoint {
            id: "create_user".to_string(),
            param_names: vec![],
        };
        insert_route(&mut root, &parse_pattern("/users"), 0, "POST", ep2);

        let mut values = Vec::new();
        assert_eq!(
            match_segments(&root, &["users"], 0, "GET", &mut values)
                .unwrap()
                .id,
            "list_users"
        );
        assert_eq!(
            match_segments(&root, &["users"], 0, "POST", &mut values)
                .unwrap()
                .id,
            "create_user"
        );
        assert!(match_segments(&root, &["users"], 0, "DELETE", &mut values).is_none());
    }

    #[test]
    fn test_root_path() {
        let mut root = Node::new("");
        let endpoint = Endpoint {
            id: "root".to_string(),
            param_names: vec![],
        };
        insert_route(&mut root, &parse_pattern("/"), 0, "GET", endpoint);

        let mut values = Vec::new();
        let result = match_segments(&root, &[], 0, "GET", &mut values);
        assert!(result.is_some());
        assert_eq!(result.unwrap().id, "root");
    }
}
