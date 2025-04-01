<script>jQuery(document).click(function (event) { var target = jQuery(event.target); if (target.attr('src') && target.parents('.image').length && target.parents('.widget').length) { var text = target.attr('title');  if (!text.length) { text = "N/A"; } ga('send', { hitType: 'event', eventCategory: 'Image', eventAction: 'Image - ' + text, eventLabel: window.location.href }); } if (target.is('button') || target.hasClass('button') || target.parents().hasClass('button')) { var text = ""; if (target.parents('.button')[0]) { text = target.parents('.button').first().text(); } else if (target.text().length) { text = target.text(); } else if (target.attr('title').length) { text = target.attr('title'); } if (!text.length) { text = "N/A"; } ga('send', { hitType: 'event', eventCategory: 'Button', eventAction: 'Button - ' + text, eventLabel: window.location.href }); } if (target.parents('.widgetCustomHtml').length) { ga('send', { hitType: 'event', eventCategory: 'Custom Html', eventAction: 'Custom Html Clicked', eventLabel: window.location.href }); } if (target.parents('.editor').length) { ga('send', { hitType: 'event', eventCategory: 'Editor', eventAction: 'Editor Link Clicked', eventLabel: window.location.href }); } if (target.parents('.GraphicLinks').length) { var text = ""; var targetGraphicLink = target; if (target.hasClass('widgetGraphicLinksLink')) { targetGraphicLink = jQuery(target.children()[0]); } if (targetGraphicLink.hasClass('text')) { text = targetGraphicLink.text(); } else if (targetGraphicLink.attr('src').length) { if (targetGraphicLink.attr('alt').length) { text = targetGraphicLink.attr('alt'); } else { text = targetGraphicLink.attr('src'); } } else { text = "N/A"; } ga('send', { hitType: 'event', eventCategory: 'Graphic Links', eventAction: 'Graphic Link - ' + text, eventLabel: window.location.href }); } if (target.parents('.InfoAdvanced').length) { ga('send', { hitType: 'event', eventCategory: 'Info Advanced', eventAction: 'Info Advanced Clicked', eventLabel: window.location.href }); } if (target.parents('.list').length) { ga('send', { hitType: 'event', eventCategory: 'List', eventAction: 'List Clicked', eventLabel: window.location.href }); } if (target.parents('.megaMenuItem').length || target.parents('.topMenuItem').length) { var megaMenuText = jQuery('.topMenuItem.mouseover').find('span').text(); var breadCrumbs = []; jQuery('.breadCrumbs > li').each(function () {  breadCrumbs.push(this.textContent); }); var pageTitle = breadCrumbs.join('>'); var subTitleText = target.parents('.megaMenuItem').children('.widgetTitle').children().text(); var text = ""; if (pageTitle) { text += pageTitle + " | "; } else { text += document.title + ' - '; } if (target.text() == "" && megaMenuText == "") { text += "N/A"; } else if (target.text().length && megaMenuText.length) { if (megaMenuText == target.text()) { text += megaMenuText; } else { text += megaMenuText + " - " + subTitleText + " - " + target.text(); } } else if (target.text() == "") { text += megaMenuText; } else { text += target.text(); } if (!text.length) { text = "N/A"; } ga('send', { hitType: 'event', eventCategory: 'Mega Menu', eventAction: 'Mega Menu : ' + text, eventLabel: window.location.href }); } if (target.parents('.widgetNewsFlash').length && target.parents('.widgetItem').length) { var text = jQuery(target.parents('.widgetItem')[0]).find('.widgetTitle').children().text(); if (!text.length) { text = "N/A"; } ga('send', { hitType: 'event', eventCategory: 'News Flash', eventAction: 'News Flash - ' + text, eventLabel: window.location.href }); } if (target.hasClass('widgetQuickLinksLink') || target.find('.widgetQuickLinksLink').length) { var text = target.text(); if (!text.length) { text = "N/A"; } ga('send', { hitType: 'event', eventCategory: 'Quick Links', eventAction: 'Quick Links - ' + text, eventLabel: window.location.href }); } if (target.attr('src') && target.parents('.cpSlideshow').length) { var text = target.attr('title'); if (!text.length) { text = "N/A"; } ga('send', { hitType: 'event', eventCategory: 'Slideshow', eventAction: 'Slideshow - ' + text, eventLabel: window.location.href }); } if (target.parents('.widgetText').length) { ga('send', { hitType: 'event', eventCategory: 'Text', eventAction: 'Text Link Clicked', eventLabel: window.location.href }); }});</script>  [Skip to Main Content](https://www.spokanevalleywa.gov/314/Housing-Homelessness#cc5f8c90dc-b4cb-431b-90ee-10648f8df655)   [![Home Page](images/0ad9a8c94aa440cc4df299174e9931c543b1e622fc867ea7277fd0af7847c0ce)](https://www.spokanevalleywa.gov/314/Housing-Homelessness)   [City

Home](https://www.spokanevalleywa.gov)   [![Facebook](images/f75fe6b2979150f27a65063a45dbac12cb171f396bc24955a51d5e5defb17ca0)](https://www.facebook.com/CityofSpokaneValley)   [![X](images/d0fe2b098c04be543d26e00ab1bb534b0b5d55a572d8ce33a85fd54e4fbee539)](https://x.com/CityofSV)   [![Instagram](images/bfc2ef8c5004f63148ccd7fd8aaaa4868631322e5348decd83a385f3ae66d6a2)](https://www.instagram.com/cityspokanevalley)   [![YouTube](images/8335cb2aaec79833d44df2341de759285c86be49875c599b70ec9f7b0e600f0d)](https://www.youtube.com/channel/UCoNlPNd0y5U905mvDfEmn7g)  <script defer type="text/javascript" src="/Common/Controls/jquery-ui-1.14.1/jquery-ui.min.js"></script><script defer src="/Areas/Layout/Assets/Scripts/Search.js" type="text/javascript"></script><script defer type="text/javascript"> $(document).ready(function () { try { $(".widgetSearchButton.widgetSearchButton0b507170-a549-4f5f-bc51-9b5f4d5180ba").click(function (e) { e.preventDefault(); if (false||$("#ysnSearchOnlyDept0b507170-a549-4f5f-bc51-9b5f4d5180ba").is(':checked')) { doWidgetSearch($(this).siblings(".widgetSearchBox").val(), Number(0)); } else { doWidgetSearch($(this).siblings(".widgetSearchBox").val(), 0); } }); $("#searchField0b507170-a549-4f5f-bc51-9b5f4d5180ba").keypress(function (e) { if (window.clipboardData) { if (e.keyCode === 13) { if ($("#ysnSearchOnlyDept0b507170-a549-4f5f-bc51-9b5f4d5180ba").is(':checked') || false) { doWidgetSearch($(this).val(), Number(0)); } else { doWidgetSearch($(this).val(), 0); } return false; } } else { if (e.which === 13) { if ($("#ysnSearchOnlyDept0b507170-a549-4f5f-bc51-9b5f4d5180ba").is(':checked') || false) { doWidgetSearch($(this).val(), Number(0)); } else { doWidgetSearch($(this).val(), 0); } return false; } } return true; }); if (true) { var currentRequest = null; var $searchField = $("#searchField0b507170-a549-4f5f-bc51-9b5f4d5180ba").autocomplete({ source: function (request, response) { currentRequest = $.ajax({ url: '/Search/AutoComplete' + ($("#ysnSearchOnlyDept0b507170-a549-4f5f-bc51-9b5f4d5180ba").is(':checked') || false? '?departmentId=0' : ''), dataType: "json", timeout: 10000, beforeSend: function () { if (currentRequest != null) { currentRequest.abort(); } }, data: { term: request.term, }, success: function (data) { response(data); $('.autoCompleteError').remove(); }, error: function (xmlhttprequest, textstatus, message) { if (textstatus === "timeout") { if ($("#searchField0b507170-a549-4f5f-bc51-9b5f4d5180ba").siblings('.autoCompleteError').length == 0) $('<span class="autoCompleteError"><p class="alert error">Search autocomplete is currently not responding. Please try again later.</p></span>').insertAfter($("#searchField0b507170-a549-4f5f-bc51-9b5f4d5180ba")); } } }); }, html: true, delay: 500, select: function (event, ui) { $(this).val(ui.item.value); $(this).next().click(); } }); $searchField.data("ui-autocomplete")._renderItem = function (ul, item) { return $("<li class=\"itemList\"></li>").data("ui-autocomplete-item", item).append("<a>" + item.label + "</a>").appendTo(ul); };}} catch(e) {} //we're going to eat this error. Autocomplete won't work but we dont wan't to break anything else on the page. }); </script>  [![Search](images/ad23c84baf3bd9c160ae4646d88f899251fe74719b13e7287c813e1fabde5475)](https://www.spokanevalleywa.gov/Search/Results) Search <script type="text/javascript"> //Updates search icons href to have the correct queryString function searchBtnApplyQuery() { document.getElementById("btnSearchIcon").href = "/Search?searchPhrase=" + document.getElementById("searchField0b507170-a549-4f5f-bc51-9b5f4d5180ba").value; } </script> 

 1.  [Government](https://www.spokanevalleywa.gov/27/Government) 
 1.  [Community](https://www.spokanevalleywa.gov/31/Community) 
 1.  [Business](https://www.spokanevalleywa.gov/101/Business) 
 1.  [Services](https://www.spokanevalleywa.gov/149/Services) 
 1.  [How Do I...](https://www.spokanevalleywa.gov/9/How-Do-I) 
<script type="text/javascript"> document.addEventListener('DOMContentLoaded',function () { var menuID = 'mainNavMenu'; var menuType = MAIN_MENU; //setup menu manager properties for main menu if (!menuManager.mobileMainNav && true) menuManager.adjustMainItemsWidth('#' + menuID); menuManager.isMainMenuEditable = false; menuManager.mainMenuMaxSubMenuLevels = 4; menuManager.setMOMMode(2, menuType); //Init main menu var setupDraggable = menuManager.isMainMenuEditable; var urlToGetHiddenMenus = '/Pages/MenuMain/HiddenMainSubMenus?pageID=1&moduleID=&themeID=1&menuContainerID=mainNav'; menuManager.setupMenu(menuID, 'mainNav', menuType, setupDraggable, urlToGetHiddenMenus); menuManager.mainMenuInit = true; menuManager.mainMenuTextResizer = false; if (1.00 > 0) menuManager.mainMenuTextResizerRatio = 1.00; if (window.isResponsiveEnabled) menuManager.mainMenuReady.resolve(); }); </script>  []()  []()  <script type="text/javascript"> $(window).on("load", function () { $.when(window.Pages.rwdSetupComplete).done(function () { renderExternalBannerSlideshow('banner1', {"BannerOptionID":2,"ThemeID":1,"SlotName":"banner1","Name":"Default","IsDefault":true,"BannerMode":2,"SlideShowSlideTiming":null,"SlideshowTransition":0,"SlideShowTransitionTiming":null,"ImageScale":true,"ImageAlignment":1,"ImageScroll":true,"MuteSound":true,"VideoType":0,"Status":40,"SlideshowControlsPosition":0,"SlideshowControlsAlignment":0,"SlideshowBannerControlsColorScheme":0,"DisplayVideoPauseButton":false,"VideoPauseButtonAlignment":1,"VideoPauseButtonControlsAlignment":0,"VideoPauseButtonStyle":"#FFFFFF","VideoPauseButtonBackgroundStyle":"#000000","VideoPauseButtonAlignmentClass":"alignRight viewport","DisplaySlideshowPauseButton":true,"SlideshowControlsColor":"#FFFFFF","SlideshowControlsBackgroundColor":"#000000","SlideshowPauseButtonClass":"isHidden","BannerImages":[{"BannerImageID":57,"BannerOptionID":2,"FileName":"/ImageRepository/Document?documentID=65","Height":700,"Width":2200,"StartingOn":null,"StoppingOn":null,"IsLink":false,"LinkAddress":null,"Sequence":1,"RecordStatus":0,"ModifiedBy":0,"ModifiedOn":"\/Date(-62135575200000)\/","AltText":""},{"BannerImageID":58,"BannerOptionID":2,"FileName":"/ImageRepository/Document?documentID=64","Height":700,"Width":2200,"StartingOn":null,"StoppingOn":null,"IsLink":false,"LinkAddress":null,"Sequence":2,"RecordStatus":0,"ModifiedBy":0,"ModifiedOn":"\/Date(-62135575200000)\/","AltText":""},{"BannerImageID":59,"BannerOptionID":2,"FileName":"/ImageRepository/Document?documentID=63","Height":700,"Width":2200,"StartingOn":null,"StoppingOn":null,"IsLink":false,"LinkAddress":null,"Sequence":3,"RecordStatus":0,"ModifiedBy":0,"ModifiedOn":"\/Date(-62135575200000)\/","AltText":""}],"BannerVideos":[],"RecordStatus":0,"ModifiedBy":0,"ModifiedOn":"\/Date(-62135575200000)\/"}, '/App_Themes/Interior/Images/', 'Rotating'); }); }); </script> 

 1.  [Home](https://www.spokanevalleywa.gov/314/Housing-Homelessness) 
 1.  [Government](https://www.spokanevalleywa.gov/27/Government) 
 1.  [Departments](https://www.spokanevalleywa.gov/186/Departments) 
 1.  [City Services](https://www.spokanevalleywa.gov/673/City-Services) 
 1. Housing & Homelessness Program

# Housing & Homelessness Program

Homelessness is a worldwide crisis that impacts Spokane Valley and our region. Ending homelessness requires a collective effort of government, non-profit, faith-based organizations, businesses and community members. 

The City works with Spokane County, City of Spokane and private and non-profit partners in a collective effort to prevent and end homelessness. [View a fact sheet about the program.](https://www.spokanevalleywa.gov/DocumentCenter/View/3275/Addressing-Homelessness-Fact-Sheet_Jan-2025) 

On Dec. 5, 2023, the City Council adopted the [Spokane Valley Homeless Action Plan](https://spokanevalleywa.gov/DocumentCenter/View/2211/Spokane-Valley-Homeless-Action-Plan?bidId=). This high-level plan provides a roadmap to address, reduce and prevent homelessness in the city.

##  __CONNECT people to resources__ 

Spokane Valley is focusing efforts on helping individuals and families who experience homelessness and want to be helped by connecting them to available resources.

###  __Outreach Team__ 

The City uses a co-deployment model, including one dedicated full-time city staff member, one homeless outreach police officer within the Spokane Valley Police Department (and beginning Dec. 1, 2024, a second homeless outreach officer), and 1.5 social workers through a contract with Frontier Behavioral Health. These individuals make up the Spokane Valley Outreach Team and work together daily to contact individuals experiencing homelessness and connect them to resources. 

##  __INVEST in services, shelters and stability __ 

###  __Shelters__ 

The City provides funding through contracts with Truth Ministries and Volunteers of America for dedicated shelter beds and support services in Spokane. If the city’s outreach team encounters someone who needs shelter, they are referred to these facilities, and transportation can be provided if needed.

The City is also part of the Spokane County consortium, along with all other cities in the county outside the City of Spokane. Through this county consortium, Spokane County administers funds for community development, affordable housing and homeless services that the Housing and Urban Development (HUD) allocates to the City, unincorporated Spokane County and other cities in the consortium. The funds are used to fund area shelters, affordable housing projects and other services for all county residents, including those from Spokane Valley.

Find links to shelter resources under Quick Links on this webpage. 

###  __Housing and Homelessness Grants__ 

Through community partnerships, the City is funding a variety of housing and homelessness projects. The Spokane Valley City Council allocated approximately [$8 million in grants for affordable housing and homeless-related projects](https://spokanevalleywa.gov/190/Grant-Funding-Opportunities). Grant recipients include:

 * $4 million grant to Partners Inland NW (formerly Spokane Valley Partners) for the acquisition of a new facility to house their food, clothing and diaper banks.
 * $1 million to Family Promise for its F.L.A.S.H.- fast leasing and sustainable housing program that provides assistance for families experiencing or soon to experience homelessness to eliminate or drastically eliminate their stay in a shelter or being unhoused.  They will also use a portion of their award to establish a family shelter in Spokane Valley
 * $1.4 million to Reclaim Project Recovery for its home base facility, operations and a transitional housing facility in Spokane Valley.  Reclaim provides a transformational platform for men transitioning away from addiction, homelessness and criminality.  They offer comprehensive support programs including recovery classes, transitional living resources, work opportunities, occupational development and an active sober community.
 * $500,000 to Volunteers of America for its Crosswalk 2.0; a youth shelter and transitional housing project. In addition to housing, this program will provide wrap-around services including counseling, medical resources, employment readiness programs, GED tutoring, etc.
 * $470,000 to Habitat for Humanity for the acquisition of property to provide affordable home-ownership opportunities in Spokane Valley
 * $470,000 to SNAP for its Broadway Senior Affordable Housing Project

##  __PARTNER to leverage funds, coordinate efforts and improve outcomes__ 

The City actively participates in regional conversations and efforts to prioritizes strategies for best investing homeless-related funding that maximize the effectiveness of the available resources in Spokane Valley and throughout the county.

###  __Housing Homelessness Assistance Act (HHAA)__ 

In August 2023, Spokane Valley began collecting and managing the Housing Homelessness Assistance Act (HHAA) money collected through real estate document recording fees. Spokane County collects these funds, but both the City of Spokane and Spokane Valley manage their own portion of the revenue.

###  __Community Advisory Boards and Funding Distribution__ 

Spokane Valley actively participates in the regional boards that assess community needs for affordable housing, homelessness and community development, including the City of Spokane Valley Homeless Housing Task Force, the Continuum of Care (CoC), Spokane County Housing and Community Development Advisory Committee, and City of Spokane Community Housing and Homeless Services (CHHS).  

###  __Addressing Homelessness for Businesses __ 

The City is working to empower businesses by providing helpful guidance and information to minimize the negative impacts that individuals experiencing homelessness and/or persons living in vehicles and tents may have on their property. Visit the [Addressing Homelessness](https://spokanevalleywa.gov/315/Addressing-Homelessness) webpage to learn more or [view the online resource](https://spokanevalleywa.gov/DocumentCenter/View/2704).

 <script type="text/javascript"> $(document).ready(function (e) {   renderSlideshowIfApplicable($('#divEditor' + '8785cab2-7857-44be-9823-480796557609')); });</script> 

###  [Contact Us](https://www.spokanevalleywa.gov/Directory.aspx) 

 1.    

#### Eric Robison   

 Housing and Homeless Coordinator  [Email Eric Robison](mailto:erobison@SpokaneValleyWA.gov)  Phone: [509-720-5048](tel:5097205048)     

### City and County Support Affordable Housing Development

 *  [Review the city’s RFP ](https://www.spokanevalleywa.gov/CivicAlerts.aspx?AID=442) 
 *  [City RFP Q&A](https://www.spokanevalleywa.gov/DocumentCenter/View/3258/Affordable-Market-Rate-Housing-RFP-Question-and-Answer-Resource)  [](https://www.spokanecounty.org/3142/Current-RFP) 
 *  [Review the county's RFP](https://www.spokanecounty.org/3142/Current-RFP) 
 *  [View the Affordable & Market Rate Housing RFP Technical Assistance Session](https://spokanevalleywa.gov/129/Agendas-Minutes-Videos) 
 *  [View the Amended Report](https://www.spokanevalleywa.gov/DocumentCenter/View/3148/Amended-Report-1---Amend-Exp-17) 
 *  [View the Carnahan Road Land Report](https://www.spokanevalleywa.gov/DocumentCenter/View/3149/WA03-24-0010-000-Carnahan-Road-Land-Report) 
 *  [View the Phase I Environmental Site Assessment](https://www.spokanevalleywa.gov/DocumentCenter/View/3150/Goodale-and-Barbieri-Spokane-Valley-Phase-I-ESA-final-with-appendices-secured) 
 <script type="text/javascript"> $(document).ready(function (e) {   renderSlideshowIfApplicable($('#divEditor' + '2b857d2e-5bf3-419f-8a0c-b3fe38d17ce9')); });</script> 

##  __Quick Links __ 

 *  [Addressing Homelessness Fact Sheet](https://www.spokanevalleywa.gov/DocumentCenter/View/3275/Addressing-Homelessness-Fact-Sheet_Jan-2025) 
 *  [Complete online resource and services directory](https://spokanevalleywa.gov/BusinessDirectoryII.aspx?lngBusinessCategoryID=37) 
 *  [Pocket Resource Guide (PDF)](https://www.spokanevalleywa.gov/DocumentCenter/View/2763/Spokane-Valley-Spokane-Pocket-Resource-Guide---July-2024) 
 *  [List of area agencies and phone numbers (PDF)](https://spokanevalleywa.gov/DocumentCenter/View/722) 

 __Day Centers and Food Banks__ 

 *  [Day drop-in centers and food banks](https://spokanevalleywa.gov/BusinessDirectoryII.aspx?lngBusinessCategoryID=23) 

 __Shelters__ 

 *  [ShelterMeSpokane.org](https://sheltermespokane.org) 
 *  [Single Adults (18 and up) (Without Children)](https://www.spokanevalleywa.gov/BusinessDirectoryII.aspx?lngBusinessCategoryID=24) 
 *  [Homeless Families (with Minor Children)](https://www.spokanevalleywa.gov/BusinessDirectoryII.aspx?lngBusinessCategoryID=25) 
 *  [Youth/Young Adult Shelters](https://www.spokanevalleywa.gov/BusinessDirectoryII.aspx?lngBusinessCategoryID=26) 

 __Housing__ 

 *  [Housing assistance](https://spokanevalleywa.gov/BusinessDirectoryII.aspx?lngBusinessCategoryID=28) (contact one)

 __Health__ 

 *  [Health and hygiene resources](https://www.spokanevalleywa.gov/BusinessDirectoryII.aspx?lngBusinessCategoryID=27) 
 *  [Addiction Help Finder](https://addictionhelpfinder.org) 

 __Other Resources__ 

 *  [Washington 2-1-1](https://wa211.org) (identifies community resources statewide)
 *  [Fig Tree Resource Guide](https://www.thefigtree.org/connections-resources.html) (online lists of area resources)
 *  [Spokane Resource Google Map](https://www.google.com/maps/d/viewer?mid=1gUeLH-YGPrslcZXzK1r5tJlOTry8EZ18&ll=48.05876727125485%2C-117.47933714999999&z=7) 
 *  [Partnering for solutions video](https://www.youtube.com/watch?v=vytF_NNmuAw) (Dec 2023)

 __Document Library__ 

 *  [Homeless Action Plan](https://www.spokanevalleywa.gov/DocumentCenter/View/2211) 
 <script type="text/javascript"> $(document).ready(function (e) {   renderSlideshowIfApplicable($('#divEditor' + '11eea07e-9c10-46e6-9334-2b6257b49457')); });</script> 

## Report a Concern

Please use our [SVexpress App](https://spokanevalleywa.gov/443/SVexpress---Report-a-Concern) to report issues related to the following:

 * Abandoned grocery carts
 * Abandoned vehicles
 * Illegal dumping
 * Accumulation of garbage
 * Sidewalk obstruction 
 * Living in RV or vehicle
 <script type="text/javascript"> $(document).ready(function (e) {   renderSlideshowIfApplicable($('#divEditor' + '1cf271a9-0783-4829-a3a3-4a1ac1053cf8')); });</script> 

 1.   [Homelessness Resource Directory](https://www.spokanevalleywa.gov/BusinessDirectoryII.aspx?lngBusinessCategoryID=37)  
 1.   [Addressing Homelessness for Businesses and Property Owners](https://www.spokanevalleywa.gov/315/Addressing-Homelessness-for-Businesses-a)  
 1.   [Five-Year Consolidated Plan](https://www.spokanevalleywa.gov/713/Five-Year-Consolidated-Plan)  
<script type="text/javascript"> window.addEventListener('load', function () { //setup menu manager properties for secondary menu menuManager.isSideMenuEditable = false; menuManager.sideMenuMaxSubMenuLevels = 4; menuManager.sideMenuHasCustomLinks = false; }); </script><script type="text/javascript"> window.addEventListener('load', function () { $('*[id^="SideItem"]').each(function () { var ids = $('[id="' + this.id + '"]'); if (ids.length > 1) $.each(ids, function (index, value) { value.id = value.id + '_' + index; }); }); $('.hasAccordionChildren.openAccordionNav').click(function (e) { e.preventDefault(); showHideAccordionMenuForSecondaryNav($(this)); }); $("#secondaryNav.grippy").each(function () { menuManager.setupDraggableElement($(this), SIDE_MENU, '#secondaryNav'); }); $("#secondaryNav li").each(function () { menuManager.setupDroppableAccordionElement($(this), SIDE_MENU); }); }); </script>  [Permit Center](https://www.spokanevalleywa.gov/180/Permit-Center)   [Police Department](https://www.spokanevalleywa.gov/169/Police)   [Parks & Recreation](https://www.spokanevalleywa.gov/163/Parks-Recreation)   [Employment](https://www.spokanevalleywa.gov/411)   [Agendas & Minutes](https://www.spokanevalleywa.gov/129/Agendas-Minutes)   [Report a Concern](https://www.spokanevalleywa.gov/443/SVexpress---Report-a-Concern)  

 1.    

 ![Home Page](images/026af6a61a5ac689510b60b6fc66b0f3f9732d306d5983a5da3be8cb6c1d79a0)    

 <script type="text/javascript"> //Render slideshow if info advacned items contain one. $(document).ready(function (e) { $('#divInfoAdv4cd3f3bf-9fee-4aaa-aa8b-3d56fdc3415a.InfoAdvanced.widgetItem').each(function () { renderSlideshowIfApplicable($(this));  }); });</script> 

### Contact Us

 1.    

 __Spokane Valley City Hall__    

10210 East Sprague Avenue   

Spokane Valley, WA 99206   

 __Phone__ : [509-720-5000](tel: 509-720-5000)    

 <script type="text/javascript"> //Render slideshow if info advacned items contain one. $(document).ready(function (e) { $('#divInfoAdvbcf5407d-f091-4078-83b2-29c769f2420b.InfoAdvanced.widgetItem').each(function () { renderSlideshowIfApplicable($(this));  }); });</script> 

###  [Quick Links](https://www.spokanevalleywa.gov/QuickLinks.aspx?CID=15) 

 1.  [News & Alerts - Subscribe](https://public.govdelivery.com/accounts/WASPOKANEVALLEY/subscriber/new?qsp=CODE_RED)  
 1.  [Public Notices](https://www.spokanevalleywa.gov/359/2154/Public-Notices)  
 1.  [Public Records Request](https://spokanevalleywa.gov/691/Public-Records)  
 1.  [Documents Archive (Laserfiche)](https://laserfiche.spokanevalley.org/WebLink/Browse.aspx?dbid=0&repo=SpokaneValley)  
 1.  [Municipal Code](https://www.codepublishing.com/WA/SpokaneValley)  
 1.  [City News](https://www.spokanevalleywa.gov/CivicAlerts.aspx?CID=1)  
 /QuickLinks.aspx 

###  [Site Links](https://www.spokanevalleywa.gov/QuickLinks.aspx?CID=16) 

 1.  [City Home](https://www.spokanevalleywa.gov)  
 1.  [Contact Us](https://www.spokanevalleywa.gov/directory.aspx)  
 1.  [Site Map](https://www.spokanevalleywa.gov/sitemap)  
 1.  [ADA Notification](https://www.spokanevalleywa.gov/207/Americans-with-Disabilities-Act-Notice)  
 1.  [Website Accessibility](https://www.spokanevalleywa.gov/accessibility)  
 1.  [Copyright Notices](https://www.spokanevalleywa.gov/copyright)  
 1.  [Privacy Policy & Data Collection](https://www.spokanevalleywa.gov/privacy)  
 /QuickLinks.aspx Loading Loading Do Not Show AgainClose <script src="/Assets/Scripts/APIClient.js"></script><script src="/Assets/Mystique/Shared/Scripts/Moment/Moment.min.js"></script><script src="/Assets/Scripts/SplashModal/SplashModalRender.js"></script><script> $(document).ready(function () { var filter = { targetId: '314', targetType: 1 } new SplashModalRender().triggerRender(filter); });</script><script src="/-1931737305.js" type="text/javascript"></script><script> function getValueTS(elem, attr) { var val = elem.css(attr); if (val === undefined) return undefined; var num = parseInt(val, 10); if (num === NaN) return undefined; return num; } function clampTS(number, min, max) { return Math.min(Math.max(number, min), max); } function isPageEditingTS() { return ( $("#doneEditing").length > 0 || // In live edit typeof DesignCenter !== "undefined" // In theme manager ); } var bgColorRegexTS = new RegExp("rgba\((\d+), (\d+), (\d+), (\d*\.?\d*)\)"); function isTransparentTS(elem) { var bg = elem.css('background-color'); if (typeof bg !== "string") return false; if (bg === "transparent") return true; if (!bg.startsWith('rgba(')) return false; var matchState = bg.match(bgColorRegexTS); if (!matchState || matchState.length !== 5) return false; var alpha = parseFloat(matchState[4], 10); if (!(alpha >= 0 && alpha < 1)) return false; return true; } function iterateLeftpads(cb) { var containersTS = $("[class^='siteWrap'],[class*=' siteWrap']"); for (var i = 0; i < containersTS.length; i++) { var containerTS = containersTS[i]; // Skip the body container and anything with data-skip-leftpad if ( containerTS.id !== "bodyContainerTS" && containerTS.getAttribute('data-skip-leftpad') === null ) { cb(containerTS); } } } function iterateRightpads(cb) { var containersTS = $("[class^='siteWrap'],[class*=' siteWrap']"); for (var i = 0; i < containersTS.length; i++) { var containerTS = containersTS[i]; // Skip the body container and anything with data-skip-rightpad if ( containerTS.id !== "bodyContainerTS" && containerTS.getAttribute('data-skip-rightpad') === null ) { cb(containerTS); } } } var anchor = $("#divToolbars"); var bodyContainerTS = $("#bodyContainerTS"); // Outer banner padding (push banner down) var outerSizingTS = $("#bannerContainerTS"); // Inner banner padding (push banner content down) - Transparent header OR on attaching headers var innerSizingTS = $("#bannerSizingTS"); var forceUnfixClassTS = "forceUnfixTS"; var fixedTopTS = $(".fixedTopTS"); var fixedBottomTS = $(".fixedBottomTS"); var fixedLeftTS = $(".fixedLeftTS"); var fixedRightTS = $(".fixedRightTS"); var initialTopTS; var topAttachTS; if (fixedTopTS && fixedTopTS.length === 1) { initialTopTS = getValueTS(fixedTopTS, 'top'); var attachment = fixedTopTS.attr('data-attach'); if (attachment) topAttachTS = $("#" + attachment); if (!topAttachTS || topAttachTS.length !== 1) topAttachTS = undefined; } function resizeAdjustmentTS() { var editing = isPageEditingTS(); // Fixed top script (function () { if (!fixedTopTS || fixedTopTS.length !== 1 || initialTopTS === undefined) return; if (editing) { fixedTopTS[0].classList.add(forceUnfixClassTS); } else { fixedTopTS[0].classList.remove(forceUnfixClassTS); } var topPosition = fixedTopTS.css('position'); if (topPosition === 'fixed') { if (topAttachTS) { scrollAdjustmentTS(); } else { var anchorHeight = anchor.outerHeight() - 1; fixedTopTS.css('top', anchorHeight + initialTopTS); } } else { fixedTopTS.css('top', initialTopTS); } if (topPosition === 'fixed' || topPosition === 'absolute') { // Bump the banner content down if (isTransparentTS(fixedTopTS)) { innerSizingTS.css('padding-top', initialTopTS + fixedTopTS.outerHeight()); outerSizingTS.css('padding-top', ''); try { window.Pages.onResizeHandlersExecute(); } catch (e) { } } else { outerSizingTS.css('padding-top', fixedTopTS.outerHeight() - 1); innerSizingTS.css('padding-top', ''); } } else { innerSizingTS.css('padding-top', ''); outerSizingTS.css('padding-top', ''); } })(); // Fixed bottom script (function () { if (!fixedBottomTS || fixedBottomTS.length === 0) return; // If the widget has gone narrow, force unfix if (editing || fixedBottomTS.outerHeight() > 200) { fixedBottomTS[0].classList.add(forceUnfixClassTS); } else { fixedBottomTS[0].classList.remove(forceUnfixClassTS); } if (fixedBottomTS.css('position') === 'fixed') { bodyContainerTS.css('padding-bottom', fixedBottomTS.outerHeight()); } else { bodyContainerTS.css('padding-bottom', ''); } })(); // Fixed left script (function () { if (!fixedLeftTS || fixedLeftTS.length === 0) return; if (editing) { fixedLeftTS[0].classList.add(forceUnfixClassTS); } else { fixedLeftTS[0].classList.remove(forceUnfixClassTS); } if (fixedLeftTS.css('position') === 'fixed') { var anchorHeight = anchor.outerHeight() - 1; fixedLeftTS.css('top', anchorHeight); var leftBoundingTS = fixedLeftTS[0].getBoundingClientRect(); iterateLeftpads(function (containerTS) { var containerBoundingTS = containerTS.getBoundingClientRect(); if (containerBoundingTS.left <= leftBoundingTS.right) { $(containerTS).css('padding-left', leftBoundingTS.width + 16); } else { $(containerTS).css('padding-left', ''); } }); } else { fixedLeftTS.css('top', ''); iterateLeftpads(function (containerTS) { $(containerTS).css('padding-left', ''); }); } })(); // Fixed right script (function () { if (!fixedRightTS || fixedRightTS.length === 0) return; if (editing) { fixedRightTS[0].classList.add(forceUnfixClassTS); } else { fixedRightTS[0].classList.remove(forceUnfixClassTS); } if (fixedRightTS.css('position') === 'fixed') { var anchorHeight = anchor.outerHeight() - 1; fixedRightTS.css('top', anchorHeight); var rightBoundingTS = fixedRightTS[0].getBoundingClientRect(); iterateRightpads(function (containerTS) { var containerBoundingTS = containerTS.getBoundingClientRect(); if (containerBoundingTS.right >= rightBoundingTS.left) { $(containerTS).css('padding-right', rightBoundingTS.width + 16); } }); } else { fixedRightTS.css('top', ''); iterateRightpads(function (containerTS) { $(containerTS).css('padding-right', ''); }); } })(); } function scrollAdjustmentTS() { if (!fixedTopTS || fixedTopTS.length !== 1 || !topAttachTS || topAttachTS.length !== 1) return; var topPosition = fixedTopTS.css('position'); if (topPosition === 'fixed' || topPosition === 'absolute') { var anchorBounding = anchor[0].getBoundingClientRect(); var attachBounding = topAttachTS[0].getBoundingClientRect(); var scrollTop = $(window).scrollTop(); fixedTopTS.css('top', Math.max(anchorBounding.bottom - 1, attachBounding.bottom)); } else { fixedTopTS.css('top', initialTopTS); } } $(window).load(function () { setTimeout(function () { try { resizeAdjustmentTS(); } catch (e) { console.error(e); } }, 350); $(window).scroll(function () { try { scrollAdjustmentTS(); } catch (e) { console.error(e); } }); var adjustTimeoutTS; $(window).resize(function () { clearTimeout(adjustTimeoutTS); adjustTimeoutTS = setTimeout(function () { try { resizeAdjustmentTS(); } catch (e) { console.error(e); } }, 350); }); $.when(window.Pages.angularToolbarComplete).done(function () { try { resizeAdjustmentTS(); } catch (e) { console.error(e); } }); });</script><script type="text/javascript"> $(function () { document.cookie = "responsiveGhost=0; path=/"; }); $(window).on("load", function () { $('body').addClass('doneLoading').removeClass('hideContent'); if ($('#404Content').length > 0) $('div#bodyWrapper').css('padding', '0px'); }); </script> <script type="text/javascript">loadCSS('//fonts.googleapis.com/css?family=DM+Serif+Display:italic,regular|Open+Sans:300,300italic,500,500italic,600,600italic,700,700italic,800,800italic,italic,regular|');</script> [] 