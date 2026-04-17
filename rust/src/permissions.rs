use pyo3::prelude::*;
use pyo3::exceptions::PyValueError;

/// A compiled permission expression stored as a tree of bitfield operations.
#[derive(Debug, Clone)]
enum Expr {
    /// Single permission bit
    Bit(u64),
    /// All sub-expressions must match (AND)
    All(Vec<Expr>),
    /// At least one sub-expression must match (OR)
    Any(Vec<Expr>),
    /// Negate the sub-expression
    Not(Box<Expr>),
}

impl Expr {
    fn evaluate(&self, user_perms: u64) -> bool {
        match self {
            Expr::Bit(mask) => (user_perms & mask) == *mask,
            Expr::All(exprs) => exprs.iter().all(|e| e.evaluate(user_perms)),
            Expr::Any(exprs) => exprs.iter().any(|e| e.evaluate(user_perms)),
            Expr::Not(expr) => !expr.evaluate(user_perms),
        }
    }
}

/// Parse a permission expression string into an Expr tree.
///
/// Grammar:
///   expr     = or_expr
///   or_expr  = and_expr ("|" and_expr)*
///   and_expr = unary ("&" unary)*
///   unary    = "!" unary | atom
///   atom     = NUMBER | "(" expr ")"
///
/// Examples:
///   "1"          → Bit(1)
///   "1 & 2"      → All([Bit(1), Bit(2)])
///   "1 | 2"      → Any([Bit(1), Bit(2)])
///   "1 & (2 | 4)" → All([Bit(1), Any([Bit(2), Bit(4)])])
///   "!1"         → Not(Bit(1))
fn parse_expression(input: &str) -> Result<Expr, String> {
    let tokens = tokenize(input)?;
    let mut pos = 0;
    let expr = parse_or(&tokens, &mut pos)?;
    if pos < tokens.len() {
        return Err(format!("Unexpected token at position {}: {:?}", pos, tokens[pos]));
    }
    Ok(expr)
}

#[derive(Debug, Clone, PartialEq)]
enum Token {
    Number(u64),
    And,
    Or,
    Not,
    LParen,
    RParen,
}

fn tokenize(input: &str) -> Result<Vec<Token>, String> {
    let mut tokens = Vec::new();
    let mut chars = input.chars().peekable();

    while let Some(&c) = chars.peek() {
        match c {
            ' ' | '\t' | '\n' | '\r' => { chars.next(); }
            '&' => { chars.next(); tokens.push(Token::And); }
            '|' => { chars.next(); tokens.push(Token::Or); }
            '!' => { chars.next(); tokens.push(Token::Not); }
            '(' => { chars.next(); tokens.push(Token::LParen); }
            ')' => { chars.next(); tokens.push(Token::RParen); }
            '0'..='9' => {
                let mut num_str = String::new();
                while let Some(&d) = chars.peek() {
                    if d.is_ascii_digit() {
                        num_str.push(d);
                        chars.next();
                    } else {
                        break;
                    }
                }
                let num: u64 = num_str.parse().map_err(|e| format!("Invalid number: {e}"))?;
                tokens.push(Token::Number(num));
            }
            _ => return Err(format!("Unexpected character: '{c}'")),
        }
    }

    Ok(tokens)
}

fn parse_or(tokens: &[Token], pos: &mut usize) -> Result<Expr, String> {
    let mut left = parse_and(tokens, pos)?;

    while *pos < tokens.len() && tokens[*pos] == Token::Or {
        *pos += 1;
        let right = parse_and(tokens, pos)?;
        left = match left {
            Expr::Any(mut exprs) => { exprs.push(right); Expr::Any(exprs) }
            _ => Expr::Any(vec![left, right]),
        };
    }

    Ok(left)
}

fn parse_and(tokens: &[Token], pos: &mut usize) -> Result<Expr, String> {
    let mut left = parse_unary(tokens, pos)?;

    while *pos < tokens.len() && tokens[*pos] == Token::And {
        *pos += 1;
        let right = parse_unary(tokens, pos)?;
        left = match left {
            Expr::All(mut exprs) => { exprs.push(right); Expr::All(exprs) }
            _ => Expr::All(vec![left, right]),
        };
    }

    Ok(left)
}

fn parse_unary(tokens: &[Token], pos: &mut usize) -> Result<Expr, String> {
    if *pos < tokens.len() && tokens[*pos] == Token::Not {
        *pos += 1;
        let expr = parse_unary(tokens, pos)?;
        return Ok(Expr::Not(Box::new(expr)));
    }
    parse_atom(tokens, pos)
}

fn parse_atom(tokens: &[Token], pos: &mut usize) -> Result<Expr, String> {
    if *pos >= tokens.len() {
        return Err("Unexpected end of expression".to_string());
    }

    match &tokens[*pos] {
        Token::Number(n) => {
            let n = *n;
            *pos += 1;
            Ok(Expr::Bit(n))
        }
        Token::LParen => {
            *pos += 1;
            let expr = parse_or(tokens, pos)?;
            if *pos >= tokens.len() || tokens[*pos] != Token::RParen {
                return Err("Expected closing ')'".to_string());
            }
            *pos += 1;
            Ok(expr)
        }
        other => Err(format!("Unexpected token: {other:?}")),
    }
}

/// Pre-compiled permission evaluator using bitfield operations.
///
/// Compile permission expressions once at startup, then evaluate in
/// nanoseconds per request. Permission values are bitmasks (powers of 2).
///
/// Usage from Python::
///
///     from django_matt._rust import PermissionEvaluator
///     evaluator = PermissionEvaluator()
///
///     # Compile expressions (returns expression ID)
///     admin_expr = evaluator.compile("1")           # bit 1 = admin
///     editor_expr = evaluator.compile("1 | 2")      # admin OR editor
///     complex = evaluator.compile("1 & (2 | 4)")    # admin AND (editor OR viewer)
///
///     # Evaluate against a user's permission bitfield
///     user_perms = 0b011  # has admin + editor
///     evaluator.evaluate(admin_expr, user_perms)     # True
///     evaluator.evaluate(complex, user_perms)        # True (1 & (2|4) → True)
#[pyclass]
pub struct PermissionEvaluator {
    expressions: Vec<Expr>,
}

#[pymethods]
impl PermissionEvaluator {
    #[new]
    fn new() -> Self {
        PermissionEvaluator {
            expressions: Vec::new(),
        }
    }

    /// Compile a permission expression and return its ID.
    ///
    /// Expression syntax:
    ///   - ``N`` — single permission bit (e.g. ``1``, ``4``, ``128``)
    ///   - ``A & B`` — both A and B required
    ///   - ``A | B`` — either A or B sufficient
    ///   - ``!A`` — A must NOT be present
    ///   - ``(...)`` — grouping
    ///
    /// Returns the expression index for use with ``evaluate()``.
    fn compile(&mut self, expression: &str) -> PyResult<usize> {
        let expr = parse_expression(expression)
            .map_err(|e| PyValueError::new_err(format!("Invalid expression: {e}")))?;
        let id = self.expressions.len();
        self.expressions.push(expr);
        Ok(id)
    }

    /// Evaluate whether a user's permission bitfield satisfies expression ``expr_id``.
    fn evaluate(&self, expr_id: usize, user_permissions: u64) -> PyResult<bool> {
        let expr = self.expressions.get(expr_id).ok_or_else(|| {
            PyValueError::new_err(format!("Unknown expression ID: {expr_id}"))
        })?;
        Ok(expr.evaluate(user_permissions))
    }

    /// Bulk-evaluate multiple expressions for one user.
    ///
    /// Returns a list of booleans in the same order as ``expr_ids``.
    fn evaluate_many(&self, expr_ids: Vec<usize>, user_permissions: u64) -> PyResult<Vec<bool>> {
        expr_ids
            .iter()
            .map(|&id| {
                let expr = self.expressions.get(id).ok_or_else(|| {
                    PyValueError::new_err(format!("Unknown expression ID: {id}"))
                })?;
                Ok(expr.evaluate(user_permissions))
            })
            .collect()
    }

    /// Return the number of compiled expressions.
    #[getter]
    fn expression_count(&self) -> usize {
        self.expressions.len()
    }
}

pub fn register(parent: &Bound<'_, PyModule>) -> PyResult<()> {
    parent.add_class::<PermissionEvaluator>()?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_single_bit() {
        let expr = parse_expression("4").unwrap();
        assert!(expr.evaluate(0b0100));
        assert!(!expr.evaluate(0b0010));
    }

    #[test]
    fn test_and() {
        let expr = parse_expression("1 & 2").unwrap();
        assert!(expr.evaluate(0b11));
        assert!(!expr.evaluate(0b01));
        assert!(!expr.evaluate(0b10));
    }

    #[test]
    fn test_or() {
        let expr = parse_expression("1 | 2").unwrap();
        assert!(expr.evaluate(0b01));
        assert!(expr.evaluate(0b10));
        assert!(expr.evaluate(0b11));
        assert!(!expr.evaluate(0b00));
    }

    #[test]
    fn test_not() {
        let expr = parse_expression("!1").unwrap();
        assert!(expr.evaluate(0b00));
        assert!(expr.evaluate(0b10));
        assert!(!expr.evaluate(0b01));
    }

    #[test]
    fn test_complex_grouped() {
        // admin AND (editor OR viewer)
        let expr = parse_expression("1 & (2 | 4)").unwrap();
        assert!(expr.evaluate(0b011));  // admin + editor
        assert!(expr.evaluate(0b101));  // admin + viewer
        assert!(!expr.evaluate(0b001)); // admin only — no editor/viewer
        assert!(!expr.evaluate(0b110)); // editor + viewer — no admin
    }

    #[test]
    fn test_nested_not() {
        // has read (1) AND does NOT have banned (8)
        let expr = parse_expression("1 & !8").unwrap();
        assert!(expr.evaluate(0b001));  // read only
        assert!(!expr.evaluate(0b1001)); // read + banned
        assert!(!expr.evaluate(0b1000)); // banned only
    }

    #[test]
    fn test_evaluator_class() {
        let mut eval = PermissionEvaluator::new();
        let id0 = eval.compile("1 & 2").unwrap();
        let id1 = eval.compile("1 | 4").unwrap();

        assert!(eval.evaluate(id0, 0b11).unwrap());
        assert!(!eval.evaluate(id0, 0b01).unwrap());
        assert!(eval.evaluate(id1, 0b01).unwrap());
        assert!(eval.evaluate(id1, 0b100).unwrap());
    }

    #[test]
    fn test_evaluate_many() {
        let mut eval = PermissionEvaluator::new();
        let id0 = eval.compile("1").unwrap();
        let id1 = eval.compile("2").unwrap();
        let id2 = eval.compile("4").unwrap();

        let results = eval.evaluate_many(vec![id0, id1, id2], 0b011).unwrap();
        assert_eq!(results, vec![true, true, false]);
    }

    #[test]
    fn test_invalid_expression() {
        assert!(parse_expression("").is_err());
        assert!(parse_expression("&").is_err());
        assert!(parse_expression("1 &").is_err());
        assert!(parse_expression("(1").is_err());
    }
}
