"""
Data models for risk map validation system.

Contains ComponentNode and ControlNode classes that represent the core
entities in the CoSAI Risk Map framework with validation and comparison logic.
"""


class ComponentNode:
    """
    Represents a component with title, category, and edge connections.
    Includes validation for data integrity.
    """

    def __init__(
        self, title: str, category: str, to_edges: list[str], from_edges: list[str], subcategory: str | None = None
    ) -> None:
        """
        Initialize component with validation.

        Args:
            title: Component name
            category: Component category
            to_edges: List of component IDs this connects to
            from_edges: List of component IDs that connect to this
            subcategory: Optional subcategory
        """
        # Validate and set the title
        if not isinstance(title, str) or not title.strip():
            raise TypeError("The 'title' must be a string consisting of at least one printing character.")
        self.title: str = title

        # Validate and set the category
        if not isinstance(category, str) or not category.strip():
            raise TypeError("The 'category' must be a string consisting of at least one printing character.")
        self.category: str = category

        # Validate and set the subcategory if it exists
        self.subcategory: str | None = None
        if isinstance(subcategory, str):
            self.subcategory = subcategory

        # Validate and set 'to_edges'
        if not isinstance(to_edges, list) or not all(isinstance(edge, str) for edge in to_edges):
            raise TypeError("The 'to_edges' must be a list of strings.")
        self.to_edges: list[str] = to_edges

        # Validate and set 'from_edges'
        if not isinstance(from_edges, list) or not all(isinstance(edge, str) for edge in from_edges):
            raise TypeError("The 'from_edges' must be a list of strings.")
        self.from_edges: list[str] = from_edges

    def __repr__(self) -> str:
        """
        Official string representation for debugging.
        """
        return (
            f"ComponentNode(title='{self.title}', "
            f"category='{self.category}', "
            f"to_edges={self.to_edges}, "
            f"from_edges={self.from_edges})"
        )

    def __str__(self) -> str:
        """
        User-friendly string representation.
        """
        return (
            f"ComponentNode '{self.title}':\n"
            f"  Category: '{self.category}'\n"
            f"  -> Connects To: {self.to_edges}\n"
            f"  <- From: {self.from_edges}"
        )

    def __eq__(self, other) -> bool:
        """
        Define equality based on title, category, and edges.
        """
        if not isinstance(other, ComponentNode):
            return NotImplemented
        return (
            self.title == other.title
            and self.category == other.category
            and self.to_edges == other.to_edges
            and self.from_edges == other.from_edges
        )


class ControlNode:
    """
    Represents a security control with metadata and relationships.

    Controls mitigate risks across AI components and are organized by category.
    Contains title, category, components, risks, and responsible personas.

    Special component values: "all" (applies to all components), "none" (no components)
    """

    def __init__(
        self,
        title: str,
        category: str,
        components: list[str],
        risks: list[str],
        personas: list[str],
    ) -> None:
        """
        Initialize control with validation.

        Args:
            title: Control title
            category: Control category (controlsData, controlsModel, etc.)
            components: Component IDs this control applies to
            risks: Risk IDs this control mitigates
            personas: Persona IDs responsible for this control
        """
        if not isinstance(title, str) or not title.strip():
            raise TypeError("Control 'title' must be a non-empty string.")
        self.title: str = title

        if not isinstance(category, str) or not category.strip():
            raise TypeError("Control 'category' must be a non-empty string.")
        self.category: str = category

        if not isinstance(components, list) or not all(isinstance(c, str) for c in components):
            raise TypeError("Control 'components' must be a list of strings.")
        self.components: list[str] = components

        if not isinstance(risks, list) or not all(isinstance(r, str) for r in risks):
            raise TypeError("Control 'risks' must be a list of strings.")
        self.risks: list[str] = risks

        if not isinstance(personas, list) or not all(isinstance(p, str) for p in personas):
            raise TypeError("Control 'personas' must be a list of strings.")
        self.personas: list[str] = personas

    def __repr__(self) -> str:
        return (
            f"ControlNode(title='{self.title}', category='{self.category}', "
            f"components={self.components}, risks={self.risks}, personas={self.personas})"
        )

    def __str__(self) -> str:
        return (
            f"Control '{self.title}':\n"
            f"  Category: {self.category}\n"
            f"  Components: {self.components}\n"
            f"  Risks: {self.risks}\n"
            f"  Personas: {self.personas}"
        )

    def __eq__(self, other) -> bool:
        """
        Define equality based on all attributes.

        Two controls are equal if all attributes match exactly (order matters for lists).
        Enables use in sets and as dictionary keys.
        """
        if not isinstance(other, ControlNode):
            return NotImplemented
        return (
            self.title == other.title
            and self.category == other.category
            and self.components == other.components
            and self.risks == other.risks
            and self.personas == other.personas
        )


class RiskNode:
    """
    Represents a risk with title and category for graph generation.
    """

    def __init__(self, title: str, category: str = "") -> None:
        """
        Initialize risk with validation.

        Args:
            title: Risk title
            category: Risk category (optional)
        """
        if not isinstance(title, str) or not title.strip():
            raise TypeError("Risk 'title' must be a non-empty string.")
        self.title: str = title

        if not isinstance(category, str):
            raise TypeError("Risk 'category' must be a string.")
        self.category: str = category

    def __repr__(self) -> str:
        return f"RiskNode(title='{self.title}', category='{self.category}')"

    def __str__(self) -> str:
        return f"Risk '{self.title}' (Category: {self.category or 'Unknown'})"
