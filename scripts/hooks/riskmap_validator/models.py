"""
Data models for risk map validation system.

Contains ComponentNode and ControlNode classes that represent the core
entities in the CoSAI Risk Map framework with validation and comparison logic.
"""


class ComponentNode:
    """
    This class encapsulates a component's title and its connections (edges)
    to and from other components. It includes validation to ensure data integrity.
    """

    def __init__(self, title: str, category: str, to_edges: list[str], from_edges: list[str]) -> None:
        """
        Initializes a Component object with validation.

        Args:
            title: The name of the component.
            to_edges: A list of component titles it connects to.
            from_edges: A list of component titles that connect to it.

        Raises:
            TypeError: If arguments are not of the expected type.
            ValueError: If the title is an empty string.
        """
        # Validate and set the title
        if not isinstance(title, str) or not title.strip():
            raise TypeError("The 'title' must be a string consisting of at least one printing character.")
        self.title: str = title

        # Validate and set the category
        if not isinstance(category, str) or not category.strip():
            raise TypeError("The 'category' must be a string consisting of at least one printing character.")
        self.category: str = category

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
        Provides an unambiguous, official string representation of the object.
        Useful for debugging.
        """
        return (
            f"ComponentNode(title='{self.title}', "
            f"category='{self.category}', "
            f"to_edges={self.to_edges}, "
            f"from_edges={self.from_edges})"
        )

    def __str__(self) -> str:
        """
        Provides a user-friendly, readable string representation of the object.
        """
        return (
            f"ComponentNode '{self.title}':\n"
            f"  Category: '{self.category}'\n"
            f"  -> Connects To: {self.to_edges}\n"
            f"  <- From: {self.from_edges}"
        )

    def __eq__(self, other) -> bool:
        """
        Defines equality between two ComponentNode objects.
        They are equal if their title, category, to_edges, and from_edges are identical.
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
    Encapsulates a control's metadata and its relationships to components and risks.

    A ControlNode represents a security or compliance control that can be applied
    to mitigate specific risks across AI system components. Controls are organized
    into categories (Data, Infrastructure, Model, Application, Assurance, Governance)
    and define which components they protect and which risks they address.

    This class is used for:
    - Storing control metadata (title, category, components, risks, personas)
    - Validating control data integrity
    - Generating control-to-component relationship graphs
    - Supporting control optimization and clustering algorithms

    Attributes:
        title (str): Human-readable name of the control
        category (str): Control category ID (e.g., 'controlsData', 'controlsModel')
        components (List[str]): List of component IDs this control applies to
        risks (List[str]): List of risk IDs this control mitigates
        personas (List[str]): List of persona IDs responsible for implementing this control

    Example:
        >>> control = ControlNode(
        ...     title="Input Validation and Sanitization",
        ...     category="controlsModel",
        ...     components=["componentInputHandling"],
        ...     risks=["PIJ"],
        ...     personas=["personaModelCreator"]
        ... )
        >>> print(control.title)
        Input Validation and Sanitization
        >>> print(len(control.components))
        1

    Note:
        - All attributes are validated for type and non-empty content during initialization
        - Component IDs should reference valid components in the system
        - Risk IDs should reference valid risks in the risk framework
        - Persona IDs should reference valid personas (Model Creator, Model Consumer)
        - Special component values "all" and "none" have specific semantic meanings
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
        Initializes a ControlNode with validation.

        Args:
            title: The control's title
            category: The control category (controlsData, controlsInfrastructure, etc.)
            components: List of component IDs this control applies to
            risks: List of risk IDs this control mitigates
            personas: List of persona IDs responsible for this control

        Raises:
            TypeError: If arguments are not of the expected type.
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
        Defines equality between two ControlNode objects.

        Two ControlNode instances are considered equal if and only if all their
        attributes (title, category, components, risks, personas) are identical.
        This enables proper comparison, deduplication, and use in collections
        like sets and dictionaries.

        Args:
            other: Object to compare with this ControlNode. Can be any type,
                  but equality will only return True for ControlNode instances.

        Returns:
            bool: True if other is a ControlNode with identical attributes,
                 False otherwise. Returns NotImplemented for non-ControlNode types
                 to allow Python's rich comparison protocol to handle the comparison.

        Example:
            >>> control1 = ControlNode("Test", "controlsData", ["comp1"], ["risk1"], ["persona1"])
            >>> control2 = ControlNode("Test", "controlsData", ["comp1"], ["risk1"], ["persona1"])
            >>> control3 = ControlNode("Different", "controlsData", ["comp1"], ["risk1"], ["persona1"])
            >>> print(control1 == control2)
            True
            >>> print(control1 == control3)
            False
            >>> print(control1 == "not a control")
            False

        Note:
            - List order matters: ["comp1", "comp2"] != ["comp2", "comp1"]
            - All attributes must match exactly (case-sensitive)
            - Empty lists are considered equal to other empty lists
            - This method enables ControlNode objects to be used in sets and as dictionary keys
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
    Encapsulates a risk's metadata for graph generation.
    Used for risk-to-control visualization.
    """

    def __init__(self, title: str, category: str = "") -> None:
        """
        Initializes a RiskNode with validation.

        Args:
            title: The risk's title
            category: The risk category (optional for now)
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
