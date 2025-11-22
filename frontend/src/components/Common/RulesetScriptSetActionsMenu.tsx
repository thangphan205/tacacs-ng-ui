import { IconButton } from "@chakra-ui/react"
import { BsThreeDotsVertical } from "react-icons/bs"
import type { RulesetScriptSetPublic } from "@/client"
import DeleteRulesetScriptSet from "../RulesetScriptSets/DeleteRulesetScriptSet"
import EditRulesetScriptSet from "../RulesetScriptSets/EditRulesetScriptSet"
import { MenuContent, MenuRoot, MenuTrigger } from "../ui/menu"

interface RulesetScriptSetActionsMenuProps {
  rulesetscriptset: RulesetScriptSetPublic
}

export const RulesetScriptSetActionsMenu = ({ rulesetscriptset }: RulesetScriptSetActionsMenuProps) => {
  return (
    <MenuRoot>
      <MenuTrigger asChild>
        <IconButton variant="ghost" color="inherit">
          <BsThreeDotsVertical />
        </IconButton>
      </MenuTrigger>
      <MenuContent>
        <EditRulesetScriptSet rulesetscriptset={rulesetscriptset} />
        <DeleteRulesetScriptSet rulesetscriptset={rulesetscriptset} />
      </MenuContent>
    </MenuRoot>
  )
}
