"""Readable schemas and extraction mappings for bounded live studies.

The category (for example, Mexican newspapers) describes why a site belongs
in a study.  The schema profile describes the record produced by the study.
Several categories may therefore share one profile without sharing URL scope
or site-specific templates.
"""
from __future__ import annotations

from typing import Any, Mapping


PROFILE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "article": {
        "title": "article observations",
        "publicationMode": "new_urls_only",
        "defaultMaxDepth": 1,
        "defaultMaxUrls": 8,
        "fields": [
            {"fieldId": "headline", "name": "headline", "type": "string"},
            {"fieldId": "canonical_url", "name": "canonical_url", "type": "url"},
            {"fieldId": "description", "name": "description", "type": "string"},
            {"fieldId": "author", "name": "author", "type": "string"},
            {"fieldId": "published_at", "name": "published_at", "type": "datetime"},
            {"fieldId": "modified_at", "name": "modified_at", "type": "datetime"},
            {"fieldId": "image_url", "name": "image_url", "type": "url"},
            {"fieldId": "section", "name": "section", "type": "string"},
            {"fieldId": "source_name", "name": "source_name", "type": "string"},
        ],
        "requiredFields": ["headline", "canonical_url"],
        "jsonld": {
            "headline": ["NewsArticle.headline", "Article.headline", "NewsArticle.name", "Article.name"],
            "canonical_url": [
                "NewsArticle.url", "Article.url", "NewsArticle.mainEntityOfPage.@id",
                "Article.mainEntityOfPage.@id",
            ],
            "description": ["NewsArticle.description", "Article.description"],
            "author": [
                "NewsArticle.author.name", "Article.author.name",
                "NewsArticle.author", "Article.author",
            ],
            "published_at": ["NewsArticle.datePublished", "Article.datePublished"],
            "modified_at": ["NewsArticle.dateModified", "Article.dateModified"],
            "image_url": [
                "NewsArticle.image.url", "Article.image.url",
                "NewsArticle.image", "Article.image",
            ],
            "section": ["NewsArticle.articleSection", "Article.articleSection"],
        },
        "meta": {
            "headline": ["og:title", "twitter:title", "<title>"],
            "canonical_url": ["og:url"],
            "description": ["og:description", "description"],
            "author": ["article:author", "author"],
            "published_at": ["article:published_time", "date"],
            "modified_at": ["article:modified_time", "og:updated_time"],
            "image_url": ["og:image", "twitter:image"],
            "section": ["article:section"],
        },
        "css": {
            "headline": ["main h1", "article h1", "h1"],
            "canonical_url": ["link[rel='canonical']@href"],
        },
    },
    "product": {
        "title": "product observations",
        "publicationMode": "append_all",
        "defaultMaxDepth": 0,
        "defaultMaxUrls": 1,
        "fields": [
            {"fieldId": "product_id", "name": "product_id", "type": "string"},
            {"fieldId": "sku", "name": "sku", "type": "string"},
            {"fieldId": "name", "name": "name", "type": "string"},
            {"fieldId": "canonical_url", "name": "canonical_url", "type": "url"},
            {"fieldId": "description", "name": "description", "type": "string"},
            {"fieldId": "brand", "name": "brand", "type": "string"},
            {"fieldId": "category", "name": "category", "type": "string"},
            {"fieldId": "color", "name": "color", "type": "string"},
            {"fieldId": "price", "name": "price", "type": "number"},
            {"fieldId": "currency", "name": "currency", "type": "string"},
            {"fieldId": "availability", "name": "availability", "type": "string"},
            {"fieldId": "image_url", "name": "image_url", "type": "url"},
            {"fieldId": "rating_value", "name": "rating_value", "type": "number"},
            {"fieldId": "rating_count", "name": "rating_count", "type": "number"},
        ],
        "requiredFields": ["name", "price", "currency"],
        "jsonld": {
            "product_id": ["Product.productID", "Product.mpn"],
            "sku": ["Product.sku"],
            "name": ["Product.name"],
            "canonical_url": ["Product.url", "Product.offers.url"],
            "description": ["Product.description"],
            "brand": ["Product.brand.name", "Product.brand"],
            "category": ["Product.category"],
            "color": ["Product.color"],
            "price": [
                "Product.offers.price", "Product.offers.lowPrice",
                "Product.hasVariant.offers.price", "Product.hasVariant.offers.lowPrice",
            ],
            "currency": [
                "Product.offers.priceCurrency",
                "Product.hasVariant.offers.priceCurrency",
            ],
            "availability": [
                "Product.offers.availability",
                "Product.hasVariant.offers.availability",
            ],
            "image_url": ["Product.image.url", "Product.image", "Product.primaryImageOfPage.contentUrl"],
            "rating_value": ["Product.aggregateRating.ratingValue"],
            "rating_count": ["Product.aggregateRating.ratingCount", "Product.aggregateRating.reviewCount"],
        },
        "meta": {
            "name": ["og:title", "twitter:title", "<title>"],
            "canonical_url": ["og:url"],
            "description": ["og:description", "description"],
            "price": ["product:price:amount", "og:price:amount"],
            "currency": ["product:price:currency", "og:price:currency"],
            "availability": ["product:availability"],
            "image_url": ["og:image", "twitter:image"],
        },
        "css": {
            "name": ["[itemprop='name']@content", "h1.product__title", "h1.product-title", "main h1"],
            "canonical_url": ["link[rel='canonical']@href"],
            "sku": ["[itemprop='sku']@content", "[data-product-sku]"],
            "price": [
                "[itemprop='price']@content", "[data-product-price]@data-product-price",
                "meta[property='product:price:amount']@content", ".price-item--sale",
                ".price-item--regular", "[data-testid*='currentPrice']",
                "[data-wk-name='purchasePodProductPrice']",
            ],
            "currency": [
                "[itemprop='priceCurrency']@content",
                "meta[property='product:price:currency']@content",
            ],
            "image_url": [
                "meta[property='og:image:secure_url']@content",
                "meta[property='og:image']@content",
            ],
        },
    },
    "job": {
        "title": "job observations",
        "publicationMode": "new_urls_only",
        "defaultMaxDepth": 1,
        "defaultMaxUrls": 6,
        "fields": [
            {"fieldId": "job_id", "name": "job_id", "type": "string"},
            {"fieldId": "title", "name": "title", "type": "string"},
            {"fieldId": "company", "name": "company", "type": "string"},
            {"fieldId": "location", "name": "location", "type": "string"},
            {"fieldId": "employment_type", "name": "employment_type", "type": "string"},
            {"fieldId": "posted_at", "name": "posted_at", "type": "datetime"},
            {"fieldId": "description", "name": "description", "type": "string"},
            {"fieldId": "canonical_url", "name": "canonical_url", "type": "url"},
        ],
        "requiredFields": ["title", "company", "canonical_url"],
        "jsonld": {
            "job_id": ["JobPosting.identifier.value", "JobPosting.identifier"],
            "title": ["JobPosting.title", "JobPosting.name"],
            "company": ["JobPosting.hiringOrganization.name"],
            "location": [
                "JobPosting.jobLocation.address.addressLocality",
                "JobPosting.jobLocation.address.addressRegion",
            ],
            "employment_type": ["JobPosting.employmentType"],
            "posted_at": ["JobPosting.datePosted"],
            "description": ["JobPosting.description"],
            "canonical_url": ["JobPosting.url"],
        },
        "meta": {
            "title": ["og:title", "twitter:title", "<title>"],
            "canonical_url": ["og:url"],
            "description": ["og:description", "description"],
        },
        "css": {
            "title": ["main h1", "article h1", "h1"],
            "canonical_url": ["link[rel='canonical']@href"],
        },
    },
    "notice": {
        "title": "public notice observations",
        "publicationMode": "new_urls_only",
        "defaultMaxDepth": 1,
        "defaultMaxUrls": 6,
        "fields": [
            {"fieldId": "notice_id", "name": "notice_id", "type": "string"},
            {"fieldId": "title", "name": "title", "type": "string"},
            {"fieldId": "agency", "name": "agency", "type": "string"},
            {"fieldId": "published_at", "name": "published_at", "type": "datetime"},
            {"fieldId": "updated_at", "name": "updated_at", "type": "datetime"},
            {"fieldId": "summary", "name": "summary", "type": "string"},
            {"fieldId": "canonical_url", "name": "canonical_url", "type": "url"},
        ],
        "requiredFields": ["title", "agency", "canonical_url"],
        "jsonld": {
            "notice_id": ["NewsArticle.identifier", "Article.identifier"],
            "title": ["NewsArticle.headline", "Article.headline", "NewsArticle.name", "Article.name"],
            "published_at": ["NewsArticle.datePublished", "Article.datePublished"],
            "updated_at": ["NewsArticle.dateModified", "Article.dateModified"],
            "summary": ["NewsArticle.description", "Article.description"],
            "canonical_url": ["NewsArticle.url", "Article.url"],
        },
        "meta": {
            "title": ["og:title", "twitter:title", "<title>"],
            "published_at": ["article:published_time", "date"],
            "updated_at": ["article:modified_time", "og:updated_time"],
            "summary": ["og:description", "description"],
            "canonical_url": ["og:url"],
        },
        "css": {
            "title": ["main h1", "article h1", "h1"],
            "canonical_url": ["link[rel='canonical']@href"],
        },
    },
    "advisory": {
        "title": "security advisory observations",
        "publicationMode": "new_urls_only",
        "defaultMaxDepth": 1,
        "defaultMaxUrls": 6,
        "fields": [
            {"fieldId": "advisory_id", "name": "advisory_id", "type": "string"},
            {"fieldId": "title", "name": "title", "type": "string"},
            {"fieldId": "vendor", "name": "vendor", "type": "string"},
            {"fieldId": "published_at", "name": "published_at", "type": "datetime"},
            {"fieldId": "updated_at", "name": "updated_at", "type": "datetime"},
            {"fieldId": "severity", "name": "severity", "type": "string"},
            {"fieldId": "summary", "name": "summary", "type": "string"},
            {"fieldId": "canonical_url", "name": "canonical_url", "type": "url"},
        ],
        "requiredFields": ["title", "vendor", "canonical_url"],
        "jsonld": {
            "advisory_id": ["TechArticle.identifier", "Article.identifier"],
            "title": ["TechArticle.headline", "Article.headline", "TechArticle.name", "Article.name"],
            "published_at": ["TechArticle.datePublished", "Article.datePublished"],
            "updated_at": ["TechArticle.dateModified", "Article.dateModified"],
            "summary": ["TechArticle.description", "Article.description"],
            "canonical_url": ["TechArticle.url", "Article.url"],
        },
        "meta": {
            "title": ["og:title", "twitter:title", "<title>"],
            "published_at": ["article:published_time", "date"],
            "updated_at": ["article:modified_time", "og:updated_time"],
            "summary": ["og:description", "description"],
            "canonical_url": ["og:url"],
        },
        "css": {
            "title": ["main h1", "article h1", "h1"],
            "canonical_url": ["link[rel='canonical']@href"],
        },
    },
    "alert": {
        "title": "weather and environmental alert observations",
        "publicationMode": "new_urls_only",
        "defaultMaxDepth": 1,
        "defaultMaxUrls": 6,
        "fields": [
            {"fieldId": "alert_id", "name": "alert_id", "type": "string"},
            {"fieldId": "title", "name": "title", "type": "string"},
            {"fieldId": "authority", "name": "authority", "type": "string"},
            {"fieldId": "issued_at", "name": "issued_at", "type": "datetime"},
            {"fieldId": "expires_at", "name": "expires_at", "type": "datetime"},
            {"fieldId": "severity", "name": "severity", "type": "string"},
            {"fieldId": "area", "name": "area", "type": "string"},
            {"fieldId": "summary", "name": "summary", "type": "string"},
            {"fieldId": "canonical_url", "name": "canonical_url", "type": "url"},
        ],
        "requiredFields": ["title", "authority", "canonical_url"],
        "jsonld": {
            "alert_id": ["SpecialAnnouncement.identifier", "Article.identifier"],
            "title": [
                "SpecialAnnouncement.name", "SpecialAnnouncement.headline",
                "Article.headline", "Article.name",
            ],
            "issued_at": ["SpecialAnnouncement.datePosted", "Article.datePublished"],
            "expires_at": ["SpecialAnnouncement.expires"],
            "summary": ["SpecialAnnouncement.text", "SpecialAnnouncement.description", "Article.description"],
            "canonical_url": ["SpecialAnnouncement.url", "Article.url"],
        },
        "meta": {
            "title": ["og:title", "twitter:title", "<title>"],
            "issued_at": ["article:published_time", "date"],
            "summary": ["og:description", "description"],
            "canonical_url": ["og:url"],
        },
        "css": {
            "title": ["main h1", "article h1", "h1"],
            "canonical_url": ["link[rel='canonical']@href"],
        },
    },
}


def profile(name: str) -> dict[str, Any]:
    """Return a supported profile or raise a readable validation error."""
    if name not in PROFILE_DEFINITIONS:
        supported = ", ".join(sorted(PROFILE_DEFINITIONS))
        raise ValueError(f"unknown live schema profile {name!r}; expected one of {supported}")
    return PROFILE_DEFINITIONS[name]


def templates_for(profile_name: str, site: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Build URL-scoped templates, allowing explicit per-site mapping overrides."""
    definition = profile(profile_name)
    scope = {
        "hosts": list(site["hosts"]),
        "urlPatterns": list(site["templatePatterns"]),
    }
    prefix = str(site["id"])
    overrides = dict(site.get("templateMappings") or {})
    constants = dict(site.get("constantFields") or {})
    templates: list[dict[str, Any]] = []
    for engine in ("jsonld", "css", "meta"):
        mappings = dict(definition.get(engine) or {})
        mappings.update(dict(overrides.get(engine) or {}))
        if not mappings:
            continue
        if engine == "meta":
            for field, value in constants.items():
                field_name = str(field)
                literal = f"literal:{value}"
                chain = list(mappings.get(field_name) or [])
                if literal not in chain:
                    chain.append(literal)
                mappings[field_name] = chain
        templates.append({
            "template_id": f"{prefix}-{profile_name}-{engine}",
            "engine": engine,
            "mappings": mappings,
            "scope": scope,
        })
    return templates


def quality_query(profile_name: str) -> str:
    """Create a compact required-field completeness query for one profile."""
    required = list(profile(profile_name)["requiredFields"])
    counts = [
        f"count(*) FILTER (WHERE {field} IS NOT NULL) AS rows_with_{field}"
        for field in required
    ]
    all_present = " AND ".join(f"{field} IS NOT NULL" for field in required)
    counts.append(
        f"count(*) FILTER (WHERE {all_present}) AS rows_with_all_required_fields"
    )
    counts.append(
        "count(DISTINCT _source_url) FILTER "
        f"(WHERE {all_present}) AS source_urls_with_all_required_fields"
    )
    return "SELECT " + ", ".join(counts) + " FROM dataset"
