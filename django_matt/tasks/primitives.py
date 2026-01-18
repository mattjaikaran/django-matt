"""
Task workflow primitives.

Provides building blocks for complex task workflows:
- Signature: Lazy task call
- Group: Run tasks in parallel
- Chain: Run tasks in sequence
- Chord: Run tasks in parallel, then a callback
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .base import Task, TaskResult


@dataclass
class Signature:
    """
    A lazy task call (signature).

    Signatures represent a task call that hasn't been executed yet.
    They can be combined into workflows using group, chain, and chord.

    Usage:
        # Create signature
        sig = add.s(2, 2)

        # Execute later
        result = sig.apply_async()

        # Or use in workflows
        chain(add.s(2, 2), multiply.s(4)).apply_async()
    """

    task: "Task"
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    options: dict = field(default_factory=dict)
    immutable: bool = False

    def apply_async(self, **options) -> "TaskResult":
        """Execute the signature asynchronously."""
        merged_options = {**self.options, **options}
        return self.task.apply_async(
            args=self.args,
            kwargs=self.kwargs,
            **merged_options,
        )

    def delay(self, *args, **kwargs) -> "TaskResult":
        """Execute with additional arguments."""
        new_args = self.args + args
        new_kwargs = {**self.kwargs, **kwargs}
        return self.task.apply_async(args=new_args, kwargs=new_kwargs)

    def apply(self, **options) -> "TaskResult":
        """Execute the signature synchronously."""
        return self.task.apply(args=self.args, kwargs=self.kwargs)

    def clone(self, args: tuple = None, kwargs: dict = None) -> "Signature":
        """Create a copy of this signature with optional modifications."""
        return Signature(
            task=self.task,
            args=args if args is not None else self.args,
            kwargs=kwargs if kwargs is not None else self.kwargs,
            options=self.options.copy(),
            immutable=self.immutable,
        )

    def set(self, **options) -> "Signature":
        """Set execution options."""
        self.options.update(options)
        return self

    def __or__(self, other: "Signature") -> "Chain":
        """Create a chain: sig1 | sig2"""
        return chain(self, other)

    def __repr__(self):
        return f"{self.task.name}({self.args}, {self.kwargs})"


def signature(
    task: "Task",
    args: tuple = None,
    kwargs: dict = None,
    **options,
) -> Signature:
    """
    Create a task signature.

    Args:
        task: The task to create a signature for
        args: Positional arguments
        kwargs: Keyword arguments
        **options: Execution options

    Returns:
        Signature instance
    """
    return Signature(
        task=task,
        args=args or (),
        kwargs=kwargs or {},
        options=options,
    )


@dataclass
class Group:
    """
    Run multiple tasks in parallel.

    Usage:
        # Run 3 tasks in parallel
        result = group(
            add.s(1, 2),
            add.s(3, 4),
            add.s(5, 6),
        ).apply_async()

        # Get results
        results = result.get()  # [3, 7, 11]
    """

    tasks: Sequence[Signature] = field(default_factory=list)

    def apply_async(self, **options) -> "GroupResult":
        """Execute all tasks in parallel."""
        from .config import get_backend

        backend = get_backend()
        return backend.send_group(self.tasks, **options)

    def apply(self, **options) -> "GroupResult":
        """Execute all tasks synchronously."""
        results = []
        for sig in self.tasks:
            results.append(sig.apply(**options))
        return GroupResult(results=results)

    def __or__(self, other: Signature) -> "Chord":
        """Create a chord: group | callback"""
        return chord(self, other)

    def __len__(self):
        return len(self.tasks)

    def __iter__(self):
        return iter(self.tasks)


def group(*tasks: Signature) -> Group:
    """
    Create a group of tasks to run in parallel.

    Args:
        *tasks: Task signatures to run in parallel

    Returns:
        Group instance

    Example:
        g = group(
            send_email.s("user1@example.com"),
            send_email.s("user2@example.com"),
            send_email.s("user3@example.com"),
        )
        g.apply_async()
    """
    return Group(tasks=list(tasks))


@dataclass
class Chain:
    """
    Run tasks in sequence, passing results forward.

    Each task receives the result of the previous task as its first argument
    (unless the signature is immutable).

    Usage:
        # Run tasks in sequence
        result = chain(
            fetch_data.s(url),
            process_data.s(),
            save_results.s(),
        ).apply_async()
    """

    tasks: Sequence[Signature] = field(default_factory=list)

    def apply_async(self, **options) -> "TaskResult":
        """Execute the chain asynchronously."""
        from .config import get_backend

        backend = get_backend()
        return backend.send_chain(self.tasks, **options)

    def apply(self, **options) -> "TaskResult":
        """Execute the chain synchronously."""
        result = None
        for sig in self.tasks:
            if result is not None and not sig.immutable:
                # Pass previous result as first argument
                new_args = (result,) + sig.args
                sig = sig.clone(args=new_args)
            task_result = sig.apply(**options)
            result = task_result.result
        return task_result

    def __or__(self, other: Signature) -> "Chain":
        """Extend the chain: chain | sig"""
        return Chain(tasks=list(self.tasks) + [other])

    def __len__(self):
        return len(self.tasks)

    def __iter__(self):
        return iter(self.tasks)


def chain(*tasks: Signature) -> Chain:
    """
    Create a chain of tasks to run in sequence.

    Args:
        *tasks: Task signatures to run in sequence

    Returns:
        Chain instance

    Example:
        c = chain(
            download_file.s(url),
            process_file.s(),
            upload_result.s(destination),
        )
        c.apply_async()
    """
    return Chain(tasks=list(tasks))


@dataclass
class Chord:
    """
    Run tasks in parallel, then run a callback with all results.

    The callback receives the list of results from the group.

    Usage:
        # Process items in parallel, then aggregate
        result = chord(
            group(
                process_item.s(1),
                process_item.s(2),
                process_item.s(3),
            ),
            aggregate_results.s(),
        ).apply_async()
    """

    header: Group
    body: Signature

    def apply_async(self, **options) -> "TaskResult":
        """Execute the chord asynchronously."""
        from .config import get_backend

        backend = get_backend()
        return backend.send_chord(self.header, self.body, **options)

    def apply(self, **options) -> "TaskResult":
        """Execute the chord synchronously."""
        # Run header (group)
        group_result = self.header.apply(**options)
        results = [r.result for r in group_result.results]

        # Run body with results
        body_args = (results,) + self.body.args
        body_sig = self.body.clone(args=body_args)
        return body_sig.apply(**options)


def chord(header: Group, body: Signature) -> Chord:
    """
    Create a chord (group + callback).

    Args:
        header: Group of tasks to run in parallel
        body: Callback task to run with all results

    Returns:
        Chord instance

    Example:
        c = chord(
            group(fetch.s(url) for url in urls),
            aggregate.s(),
        )
        c.apply_async()
    """
    return Chord(header=header, body=body)


@dataclass
class GroupResult:
    """Result of a group execution."""

    results: list["TaskResult"] = field(default_factory=list)

    def get(self, timeout: float = None, propagate: bool = True) -> list[Any]:
        """Get all results."""
        return [r.get(timeout=timeout, propagate=propagate) for r in self.results]

    @property
    def is_complete(self) -> bool:
        """Check if all tasks are complete."""
        return all(r.is_complete for r in self.results)

    def __iter__(self):
        return iter(self.results)

    def __len__(self):
        return len(self.results)
