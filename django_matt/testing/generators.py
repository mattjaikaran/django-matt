"""
Built-in data generators for testing.

Replaces Faker dependency with native Python implementations.
Provides random data generation for common types used in testing.

Usage:
    from django_matt.testing.generators import fake

    # Generate random data
    name = fake.name()
    email = fake.email()
    text = fake.paragraph()

    # With locale support
    fake.set_locale("de_DE")
    german_name = fake.name()
"""

import random
import string
import uuid
from datetime import datetime, date, time, timedelta, timezone
from typing import List, Optional, Sequence, TypeVar

T = TypeVar("T")


class RandomGenerator:
    """
    Deterministic random generator with seed support.

    Allows reproducible test data generation.
    """

    def __init__(self, seed: Optional[int] = None):
        self._random = random.Random(seed)
        self._locale = "en_US"

    def seed(self, value: int) -> None:
        """Set random seed for reproducibility."""
        self._random.seed(value)

    def set_locale(self, locale: str) -> None:
        """Set locale for localized data generation."""
        self._locale = locale

    def choice(self, seq: Sequence[T]) -> T:
        """Random choice from sequence."""
        return self._random.choice(seq)

    def choices(self, seq: Sequence[T], k: int = 1) -> List[T]:
        """Random choices with replacement."""
        return self._random.choices(seq, k=k)

    def sample(self, seq: Sequence[T], k: int) -> List[T]:
        """Random sample without replacement."""
        return self._random.sample(list(seq), k)

    def randint(self, a: int, b: int) -> int:
        """Random integer in [a, b]."""
        return self._random.randint(a, b)

    def uniform(self, a: float, b: float) -> float:
        """Random float in [a, b]."""
        return self._random.uniform(a, b)


class DataGenerator:
    """
    Built-in data generator that replaces Faker.

    Provides methods for generating common test data types.
    """

    def __init__(self, seed: Optional[int] = None):
        self._rng = RandomGenerator(seed)

        # First names (common English)
        self._first_names_male = [
            "James", "John", "Robert", "Michael", "William", "David", "Richard",
            "Joseph", "Thomas", "Charles", "Christopher", "Daniel", "Matthew",
            "Anthony", "Mark", "Donald", "Steven", "Paul", "Andrew", "Joshua",
            "Kenneth", "Kevin", "Brian", "George", "Timothy", "Ronald", "Edward",
            "Jason", "Jeffrey", "Ryan", "Jacob", "Gary", "Nicholas", "Eric",
        ]

        self._first_names_female = [
            "Mary", "Patricia", "Jennifer", "Linda", "Barbara", "Elizabeth",
            "Susan", "Jessica", "Sarah", "Karen", "Lisa", "Nancy", "Betty",
            "Margaret", "Sandra", "Ashley", "Kimberly", "Emily", "Donna",
            "Michelle", "Dorothy", "Carol", "Amanda", "Melissa", "Deborah",
            "Stephanie", "Rebecca", "Sharon", "Laura", "Cynthia", "Kathleen",
            "Amy", "Angela", "Shirley", "Anna", "Brenda", "Pamela", "Emma",
        ]

        self._last_names = [
            "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller",
            "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez",
            "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
            "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark",
            "Ramirez", "Lewis", "Robinson", "Walker", "Young", "Allen", "King",
            "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores", "Green",
        ]

        # Domain words for emails/companies
        self._domain_words = [
            "alpha", "beta", "gamma", "delta", "omega", "sigma", "tech", "data",
            "cloud", "cyber", "quantum", "neural", "pixel", "byte", "code", "dev",
            "apex", "prime", "nova", "zenith", "nexus", "vertex", "matrix", "core",
        ]

        self._tlds = ["com", "org", "net", "io", "co", "dev", "app", "ai"]

        # Lorem ipsum words for text generation
        self._lorem_words = [
            "lorem", "ipsum", "dolor", "sit", "amet", "consectetur", "adipiscing",
            "elit", "sed", "do", "eiusmod", "tempor", "incididunt", "ut", "labore",
            "et", "dolore", "magna", "aliqua", "enim", "ad", "minim", "veniam",
            "quis", "nostrud", "exercitation", "ullamco", "laboris", "nisi", "aliquip",
            "ex", "ea", "commodo", "consequat", "duis", "aute", "irure", "in",
            "reprehenderit", "voluptate", "velit", "esse", "cillum", "fugiat",
            "nulla", "pariatur", "excepteur", "sint", "occaecat", "cupidatat",
            "non", "proident", "sunt", "culpa", "qui", "officia", "deserunt",
            "mollit", "anim", "id", "est", "laborum",
        ]

        # Common company suffixes
        self._company_suffixes = [
            "Inc", "LLC", "Corp", "Ltd", "Co", "Group", "Solutions", "Systems",
            "Technologies", "Enterprises", "Industries", "Services", "Partners",
        ]

        # Street types
        self._street_types = [
            "Street", "St", "Avenue", "Ave", "Boulevard", "Blvd", "Road", "Rd",
            "Lane", "Ln", "Drive", "Dr", "Court", "Ct", "Place", "Pl", "Way",
        ]

        # US cities
        self._cities = [
            "New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia",
            "San Antonio", "San Diego", "Dallas", "San Jose", "Austin", "Jacksonville",
            "Fort Worth", "Columbus", "Charlotte", "San Francisco", "Indianapolis",
            "Seattle", "Denver", "Boston", "Portland", "Las Vegas", "Detroit", "Miami",
        ]

        # US states
        self._states = [
            ("AL", "Alabama"), ("AK", "Alaska"), ("AZ", "Arizona"), ("AR", "Arkansas"),
            ("CA", "California"), ("CO", "Colorado"), ("CT", "Connecticut"),
            ("DE", "Delaware"), ("FL", "Florida"), ("GA", "Georgia"), ("HI", "Hawaii"),
            ("ID", "Idaho"), ("IL", "Illinois"), ("IN", "Indiana"), ("IA", "Iowa"),
            ("KS", "Kansas"), ("KY", "Kentucky"), ("LA", "Louisiana"), ("ME", "Maine"),
            ("MD", "Maryland"), ("MA", "Massachusetts"), ("MI", "Michigan"),
            ("MN", "Minnesota"), ("MS", "Mississippi"), ("MO", "Missouri"),
            ("MT", "Montana"), ("NE", "Nebraska"), ("NV", "Nevada"),
            ("NH", "New Hampshire"), ("NJ", "New Jersey"), ("NM", "New Mexico"),
            ("NY", "New York"), ("NC", "North Carolina"), ("ND", "North Dakota"),
            ("OH", "Ohio"), ("OK", "Oklahoma"), ("OR", "Oregon"), ("PA", "Pennsylvania"),
            ("RI", "Rhode Island"), ("SC", "South Carolina"), ("SD", "South Dakota"),
            ("TN", "Tennessee"), ("TX", "Texas"), ("UT", "Utah"), ("VT", "Vermont"),
            ("VA", "Virginia"), ("WA", "Washington"), ("WV", "West Virginia"),
            ("WI", "Wisconsin"), ("WY", "Wyoming"),
        ]

    def seed(self, value: int) -> None:
        """Set random seed for reproducible data."""
        self._rng.seed(value)

    def set_locale(self, locale: str) -> None:
        """Set locale for localized data generation."""
        self._rng.set_locale(locale)

    # --- Name generation ---

    def first_name(self, gender: Optional[str] = None) -> str:
        """Generate a random first name."""
        if gender == "male":
            return self._rng.choice(self._first_names_male)
        elif gender == "female":
            return self._rng.choice(self._first_names_female)
        else:
            all_names = self._first_names_male + self._first_names_female
            return self._rng.choice(all_names)

    def first_name_male(self) -> str:
        """Generate a male first name."""
        return self.first_name("male")

    def first_name_female(self) -> str:
        """Generate a female first name."""
        return self.first_name("female")

    def last_name(self) -> str:
        """Generate a random last name."""
        return self._rng.choice(self._last_names)

    def name(self, gender: Optional[str] = None) -> str:
        """Generate a full name (first + last)."""
        return f"{self.first_name(gender)} {self.last_name()}"

    def name_male(self) -> str:
        """Generate a male full name."""
        return self.name("male")

    def name_female(self) -> str:
        """Generate a female full name."""
        return self.name("female")

    # --- Internet ---

    def email(self, domain: Optional[str] = None) -> str:
        """Generate a random email address."""
        first = self.first_name().lower()
        last = self.last_name().lower()
        sep = self._rng.choice([".", "_", ""])
        num = self._rng.randint(1, 999) if self._rng.randint(0, 1) else ""

        if domain is None:
            domain = f"{self._rng.choice(self._domain_words)}.{self._rng.choice(self._tlds)}"

        return f"{first}{sep}{last}{num}@{domain}"

    def safe_email(self) -> str:
        """Generate an email with a safe example domain."""
        return self.email(domain="example.com")

    def username(self) -> str:
        """Generate a random username."""
        first = self.first_name().lower()
        num = self._rng.randint(1, 9999)
        return f"{first}{num}"

    def password(
        self,
        length: int = 12,
        special_chars: bool = True,
        digits: bool = True,
        upper_case: bool = True,
        lower_case: bool = True,
    ) -> str:
        """Generate a random password."""
        chars = ""
        if lower_case:
            chars += string.ascii_lowercase
        if upper_case:
            chars += string.ascii_uppercase
        if digits:
            chars += string.digits
        if special_chars:
            chars += "!@#$%^&*"

        if not chars:
            chars = string.ascii_letters + string.digits

        return "".join(self._rng.choices(chars, k=length))

    def url(self, schemes: Optional[List[str]] = None) -> str:
        """Generate a random URL."""
        scheme = self._rng.choice(schemes or ["https"])
        domain = f"{self._rng.choice(self._domain_words)}.{self._rng.choice(self._tlds)}"
        path = "/".join(self._rng.choices(self._domain_words, k=self._rng.randint(1, 3)))
        return f"{scheme}://{domain}/{path}"

    def domain_name(self) -> str:
        """Generate a random domain name."""
        return f"{self._rng.choice(self._domain_words)}.{self._rng.choice(self._tlds)}"

    def ipv4(self) -> str:
        """Generate a random IPv4 address."""
        return ".".join(str(self._rng.randint(0, 255)) for _ in range(4))

    def ipv6(self) -> str:
        """Generate a random IPv6 address."""
        return ":".join(f"{self._rng.randint(0, 65535):x}" for _ in range(8))

    def mac_address(self) -> str:
        """Generate a random MAC address."""
        return ":".join(f"{self._rng.randint(0, 255):02x}" for _ in range(6))

    def user_agent(self) -> str:
        """Generate a random user agent string."""
        browsers = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1",
        ]
        return self._rng.choice(browsers)

    # --- Text ---

    def word(self) -> str:
        """Generate a random word."""
        return self._rng.choice(self._lorem_words)

    def words(self, nb: int = 3) -> List[str]:
        """Generate random words."""
        return self._rng.choices(self._lorem_words, k=nb)

    def sentence(self, nb_words: int = 6) -> str:
        """Generate a random sentence."""
        words = self.words(nb_words)
        words[0] = words[0].capitalize()
        return " ".join(words) + "."

    def sentences(self, nb: int = 3) -> List[str]:
        """Generate random sentences."""
        return [self.sentence() for _ in range(nb)]

    def paragraph(self, nb_sentences: int = 3) -> str:
        """Generate a random paragraph."""
        return " ".join(self.sentences(nb_sentences))

    def paragraphs(self, nb: int = 3) -> List[str]:
        """Generate random paragraphs."""
        return [self.paragraph() for _ in range(nb)]

    def text(self, max_nb_chars: int = 200) -> str:
        """Generate random text up to max characters."""
        result = ""
        while len(result) < max_nb_chars:
            result += self.sentence() + " "
            if len(result) >= max_nb_chars:
                break
        return result[:max_nb_chars].strip()

    # --- Numbers ---

    def random_int(self, min: int = 0, max: int = 9999) -> int:
        """Generate a random integer."""
        return self._rng.randint(min, max)

    def random_digit(self) -> int:
        """Generate a random digit (0-9)."""
        return self._rng.randint(0, 9)

    def random_digit_not_null(self) -> int:
        """Generate a random digit (1-9)."""
        return self._rng.randint(1, 9)

    def random_float(self, min: float = 0.0, max: float = 1.0, precision: int = 2) -> float:
        """Generate a random float."""
        return round(self._rng.uniform(min, max), precision)

    def pyfloat(
        self,
        left_digits: int = 5,
        right_digits: int = 2,
        positive: bool = True,
    ) -> float:
        """Generate a random Python float."""
        sign = 1 if positive else self._rng.choice([1, -1])
        left = self._rng.randint(0, 10**left_digits - 1)
        right = self._rng.randint(0, 10**right_digits - 1)
        return sign * float(f"{left}.{right:0{right_digits}d}")

    def pydecimal(
        self,
        left_digits: int = 5,
        right_digits: int = 2,
        positive: bool = True,
    ) -> str:
        """Generate a random decimal as string."""
        return str(self.pyfloat(left_digits, right_digits, positive))

    def pyint(self, min_value: int = 0, max_value: int = 9999) -> int:
        """Generate a random integer."""
        return self._rng.randint(min_value, max_value)

    def pybool(self) -> bool:
        """Generate a random boolean."""
        return self._rng.choice([True, False])

    # --- Date/Time ---

    def date_this_year(self) -> date:
        """Generate a random date in the current year."""
        today = date.today()
        start = date(today.year, 1, 1)
        days = (today - start).days
        return start + timedelta(days=self._rng.randint(0, days))

    def date_this_month(self) -> date:
        """Generate a random date in the current month."""
        today = date.today()
        start = date(today.year, today.month, 1)
        days = (today - start).days
        return start + timedelta(days=self._rng.randint(0, max(days, 1)))

    def date_between(self, start_date: date, end_date: date) -> date:
        """Generate a random date between two dates."""
        days = (end_date - start_date).days
        return start_date + timedelta(days=self._rng.randint(0, max(days, 1)))

    def date_of_birth(self, minimum_age: int = 18, maximum_age: int = 90) -> date:
        """Generate a random date of birth."""
        today = date.today()
        start = today - timedelta(days=maximum_age * 365)
        end = today - timedelta(days=minimum_age * 365)
        return self.date_between(start, end)

    def past_date(self, start_date: Optional[date] = None) -> date:
        """Generate a random date in the past."""
        today = date.today()
        start = start_date or date(today.year - 10, 1, 1)
        return self.date_between(start, today - timedelta(days=1))

    def future_date(self, end_date: Optional[date] = None) -> date:
        """Generate a random date in the future."""
        today = date.today()
        end = end_date or date(today.year + 10, 12, 31)
        return self.date_between(today + timedelta(days=1), end)

    def time_object(self) -> time:
        """Generate a random time."""
        return time(
            self._rng.randint(0, 23),
            self._rng.randint(0, 59),
            self._rng.randint(0, 59),
        )

    def datetime_this_year(self) -> datetime:
        """Generate a random datetime in the current year."""
        d = self.date_this_year()
        t = self.time_object()
        return datetime.combine(d, t)

    def datetime_between(self, start: datetime, end: datetime) -> datetime:
        """Generate a random datetime between two datetimes."""
        delta = end - start
        random_seconds = self._rng.randint(0, int(delta.total_seconds()))
        return start + timedelta(seconds=random_seconds)

    def past_datetime(self, start: Optional[datetime] = None) -> datetime:
        """Generate a random datetime in the past."""
        now = datetime.now(timezone.utc)
        start = start or now - timedelta(days=365 * 10)
        return self.datetime_between(start, now - timedelta(seconds=1))

    def future_datetime(self, end: Optional[datetime] = None) -> datetime:
        """Generate a random datetime in the future."""
        now = datetime.now(timezone.utc)
        end = end or now + timedelta(days=365 * 10)
        return self.datetime_between(now + timedelta(seconds=1), end)

    def iso8601(self) -> str:
        """Generate a random ISO 8601 datetime string."""
        return self.datetime_this_year().isoformat()

    def unix_time(self) -> int:
        """Generate a random Unix timestamp."""
        return int(self.datetime_this_year().timestamp())

    # --- Address ---

    def street_address(self) -> str:
        """Generate a random street address."""
        number = self._rng.randint(1, 9999)
        street_type = self._rng.choice(self._street_types)
        name = self.last_name()
        return f"{number} {name} {street_type}"

    def city(self) -> str:
        """Generate a random city name."""
        return self._rng.choice(self._cities)

    def state(self) -> str:
        """Generate a random state name."""
        return self._rng.choice(self._states)[1]

    def state_abbr(self) -> str:
        """Generate a random state abbreviation."""
        return self._rng.choice(self._states)[0]

    def postcode(self) -> str:
        """Generate a random postal code."""
        return f"{self._rng.randint(10000, 99999)}"

    def zipcode(self) -> str:
        """Generate a random ZIP code."""
        return self.postcode()

    def country(self) -> str:
        """Generate a random country name."""
        countries = [
            "United States", "Canada", "United Kingdom", "Australia", "Germany",
            "France", "Japan", "Brazil", "India", "Mexico", "China", "Italy",
            "Spain", "Netherlands", "Sweden", "Norway", "Denmark", "Finland",
        ]
        return self._rng.choice(countries)

    def country_code(self) -> str:
        """Generate a random country code."""
        codes = ["US", "CA", "GB", "AU", "DE", "FR", "JP", "BR", "IN", "MX"]
        return self._rng.choice(codes)

    def address(self) -> str:
        """Generate a full address."""
        return f"{self.street_address()}\n{self.city()}, {self.state_abbr()} {self.postcode()}"

    # --- Company ---

    def company(self) -> str:
        """Generate a random company name."""
        patterns = [
            lambda: f"{self.last_name()} {self._rng.choice(self._company_suffixes)}",
            lambda: f"{self.last_name()} and {self.last_name()}",
            lambda: f"{self.last_name()}-{self.last_name()} {self._rng.choice(self._company_suffixes)}",
            lambda: f"{self._rng.choice(self._domain_words).capitalize()} {self._rng.choice(self._company_suffixes)}",
        ]
        return self._rng.choice(patterns)()

    def company_suffix(self) -> str:
        """Generate a random company suffix."""
        return self._rng.choice(self._company_suffixes)

    def job(self) -> str:
        """Generate a random job title."""
        prefixes = ["Senior", "Junior", "Lead", "Chief", "Head", "Principal", "Staff", ""]
        roles = [
            "Software Engineer", "Developer", "Designer", "Manager", "Analyst",
            "Consultant", "Administrator", "Specialist", "Coordinator", "Director",
            "Architect", "Scientist", "Engineer", "Executive", "Officer",
        ]
        prefix = self._rng.choice(prefixes)
        role = self._rng.choice(roles)
        return f"{prefix} {role}".strip()

    # --- Identifiers ---

    def uuid4(self) -> str:
        """Generate a random UUID4."""
        return str(uuid.uuid4())

    def md5(self) -> str:
        """Generate a random MD5-like hash."""
        return "".join(self._rng.choices("0123456789abcdef", k=32))

    def sha1(self) -> str:
        """Generate a random SHA1-like hash."""
        return "".join(self._rng.choices("0123456789abcdef", k=40))

    def sha256(self) -> str:
        """Generate a random SHA256-like hash."""
        return "".join(self._rng.choices("0123456789abcdef", k=64))

    # --- Phone ---

    def phone_number(self) -> str:
        """Generate a random phone number."""
        area = self._rng.randint(200, 999)
        exchange = self._rng.randint(200, 999)
        subscriber = self._rng.randint(1000, 9999)
        return f"({area}) {exchange}-{subscriber}"

    def msisdn(self) -> str:
        """Generate a random MSISDN (international phone number)."""
        country = self._rng.randint(1, 99)
        number = "".join(str(self._rng.randint(0, 9)) for _ in range(10))
        return f"+{country}{number}"

    # --- Finance ---

    def credit_card_number(self) -> str:
        """Generate a random (fake) credit card number."""
        prefix = self._rng.choice(["4", "51", "52", "53", "54", "55", "34", "37"])
        remaining = 16 - len(prefix)
        return prefix + "".join(str(self._rng.randint(0, 9)) for _ in range(remaining))

    def credit_card_expire(self) -> str:
        """Generate a random credit card expiration date."""
        month = self._rng.randint(1, 12)
        year = date.today().year + self._rng.randint(1, 5)
        return f"{month:02d}/{year % 100:02d}"

    def credit_card_security_code(self, length: int = 3) -> str:
        """Generate a random credit card security code."""
        return "".join(str(self._rng.randint(0, 9)) for _ in range(length))

    def iban(self) -> str:
        """Generate a random (fake) IBAN."""
        country = "DE"
        check = f"{self._rng.randint(10, 99)}"
        bank = "".join(str(self._rng.randint(0, 9)) for _ in range(8))
        account = "".join(str(self._rng.randint(0, 9)) for _ in range(10))
        return f"{country}{check}{bank}{account}"

    def currency_code(self) -> str:
        """Generate a random currency code."""
        codes = ["USD", "EUR", "GBP", "JPY", "CAD", "AUD", "CHF", "CNY"]
        return self._rng.choice(codes)

    def price(self, minimum: float = 0.99, maximum: float = 999.99) -> str:
        """Generate a random price."""
        return f"{self._rng.uniform(minimum, maximum):.2f}"

    # --- Color ---

    def hex_color(self) -> str:
        """Generate a random hex color."""
        return f"#{self._rng.randint(0, 0xFFFFFF):06x}"

    def rgb_color(self) -> tuple:
        """Generate a random RGB color tuple."""
        return (
            self._rng.randint(0, 255),
            self._rng.randint(0, 255),
            self._rng.randint(0, 255),
        )

    def color_name(self) -> str:
        """Generate a random color name."""
        colors = [
            "red", "blue", "green", "yellow", "orange", "purple", "pink", "brown",
            "black", "white", "gray", "cyan", "magenta", "lime", "navy", "teal",
            "maroon", "olive", "silver", "aqua", "coral", "crimson", "gold",
        ]
        return self._rng.choice(colors)

    # --- File ---

    def file_name(self, extension: Optional[str] = None) -> str:
        """Generate a random file name."""
        name = "_".join(self._rng.choices(self._lorem_words, k=2))
        ext = extension or self._rng.choice(["txt", "pdf", "doc", "png", "jpg"])
        return f"{name}.{ext}"

    def file_extension(self) -> str:
        """Generate a random file extension."""
        return self._rng.choice(["txt", "pdf", "doc", "docx", "xls", "xlsx", "png", "jpg", "gif"])

    def mime_type(self) -> str:
        """Generate a random MIME type."""
        types = [
            "text/plain", "text/html", "text/css", "application/json",
            "application/pdf", "image/png", "image/jpeg", "image/gif",
            "audio/mpeg", "video/mp4", "application/octet-stream",
        ]
        return self._rng.choice(types)

    # --- Boolean ---

    def boolean(self, chance_of_getting_true: int = 50) -> bool:
        """Generate a random boolean with configurable probability."""
        return self._rng.randint(1, 100) <= chance_of_getting_true

    # --- Collections ---

    def random_element(self, elements: Sequence[T]) -> T:
        """Get a random element from a sequence."""
        return self._rng.choice(elements)

    def random_elements(self, elements: Sequence[T], length: int = 3) -> List[T]:
        """Get random elements from a sequence (with replacement)."""
        return self._rng.choices(elements, k=length)

    def random_sample(self, elements: Sequence[T], length: int = 3) -> List[T]:
        """Get random unique elements from a sequence (without replacement)."""
        return self._rng.sample(elements, min(length, len(elements)))


# Create a default instance for convenience
fake = DataGenerator()

# Export functions that mirror Faker's interface
__all__ = [
    "DataGenerator",
    "RandomGenerator",
    "fake",
]
